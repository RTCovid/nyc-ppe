import collections
import datetime
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Callable, NamedTuple, Set

from django.db.models import Sum
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
import django_tables2 as tables

import ppe.dataclasses as dc
from ppe.dataclasses import Period, OrderType
from ppe.models import (
    ScheduledDelivery,
    Inventory,
    FacilityDelivery,
    Demand,
    Purchase,
    current_as_of,
)
# NY Forecast from https://covid19.healthdata.org/united-states-of-america/new-york
from ppe.utils import log_db_queries

HOSPITALIZATION = {}
with open("../public-data/hospitalization_projection_new_york.json", "r") as f:
    HOSPITALIZATION = json.load(f)
ALL_BEDS_AVAILABLE = 20420
DEMAND_MESSAGE = (
    "Demand projected based on multiple sources and hospitalization models."
)


class AggColumn(str, Enum):
    Donation = "donated"
    Made = "made"
    Ordered = "ordered"
    Inventory = "inventory"

    @classmethod
    def all(cls):
        return {cls.Donation, cls.Made, cls.Ordered, cls.Inventory}


class DemandCalculationConfig(NamedTuple):
    use_real_demand: bool = True
    use_hospitalization_projection: bool = False
    rollup_fn: Callable[[dc.Item], str] = lambda x: x


class DemandSrc(str, Enum):
    past_deliveries = "PAST_DELIVERIES"
    real_demand = "LIVE_DEMAND"

    def display(self):
        if self == DemandSrc.past_deliveries:
            return "previous deliveries"
        elif self == DemandSrc.real_demand:
            return "supply burndown information"


@dataclass
class AssetRollup:
    asset: str
    total_cols: Set["AggColumn"]
    demand: int = 0
    demand_src: Set[DemandSrc] = field(default_factory=set)
    donated: int = 0
    ordered: int = 0
    made: int = 0
    inventory: int = 0

    def _value_at(self, agg_column: AggColumn):
        if agg_column == AggColumn.Made:
            return self.made
        elif agg_column == AggColumn.Ordered:
            return self.ordered
        elif agg_column == AggColumn.Inventory:
            return self.inventory
        elif agg_column == AggColumn.Donation:
            return self.donated
        else:
            raise Exception("Invalid agg column")

    @property
    def total(self):
        return sum(self._value_at(col) for col in self.total_cols)

    @property
    def absolute_balance(self):
        return self.total - self.demand

    @property
    def percent_balance(self):
        return self.absolute_balance / (self.demand + 1)

    def __add__(self, other: "AssetRollup"):
        return AssetRollup(
            asset=self.asset,
            total_cols=self.total_cols,
            demand=self.demand + other.demand,
            demand_src=self.demand_src.union(other.demand_src),
            donated=self.donated + other.donated,
            ordered=self.ordered + other.ordered,
            made=self.made + other.made,
            inventory=self.inventory + other.inventory,
        )

    def demand_src_display(self):
        if self.demand_src:
            as_list = sorted([d.display() for d in self.demand_src])
            return f'Demand from {" and ".join(as_list)}'
        else:
            return "No demand data available"


MAPPING = {
    dc.OrderType.Make: "made",
    dc.OrderType.Purchase: "ordered",
    dc.OrderType.Donation: "donated",
}


def asset_rollup_legacy(
    time_start: datetime,
    time_end: datetime,
    use_hospitalization_projection=True,
    use_real_demand=True,
    rollup_fn: Callable[[dc.Item], str] = lambda x: x,
):
    return asset_rollup(
        time_range=Period(time_start, time_end),
        supply_cols=AggColumn.all(),
        demand_calculation_config=DemandCalculationConfig(
            use_real_demand,
            use_hospitalization_projection=use_hospitalization_projection,
            rollup_fn=rollup_fn,
        ),
    )


@log_db_queries
def asset_rollup(
    time_range: Period,
    supply_cols: Set[AggColumn],
    demand_calculation_config: DemandCalculationConfig,
) -> Dict[str, AssetRollup]:
    time_start, time_end = time_range.start, time_range.end
    relevant_deliveries = (
        ScheduledDelivery.active()
        .prefetch_related("purchase")
        .filter(delivery_date__gte=time_start, delivery_date__lte=time_end)
        .exclude(purchase__order_type=OrderType.Donation)
    )

    # i'm sorry. will improve this later :)
    relevant_donations = (
        ScheduledDelivery.active()
        .prefetch_related("purchase")
        .filter(purchase__order_type=OrderType.Donation)
    )

    results: Dict[dc.Item, AssetRollup] = {}
    for _, item in dc.Item.__members__.items():
        results[item] = AssetRollup(asset=item, total_cols=supply_cols)

    for delivery in relevant_deliveries:
        rollup = results[delivery.purchase.item]
        tpe = delivery.purchase.order_type

        if tpe != dc.OrderType.Donation:
            param = MAPPING.get(tpe)

            if param is None:
                raise Exception(f"unexpected purchase type: `{tpe}`")
            setattr(rollup, param, getattr(rollup, param) + delivery.quantity)

    for donation in relevant_donations:
        rollup = results[donation.purchase.item]
        tpe = donation.purchase.order_type
        assert tpe == dc.OrderType.Donation
        param = MAPPING.get(tpe)
        setattr(rollup, param, getattr(rollup, param) + donation.quantity)

    inventory = Inventory.active()
    for item in inventory:
        rollup = results[item.item]
        rollup.inventory += item.quantity

    add_demand_estimate(time_start, time_end, results, demand_calculation_config)

    rollup_results = {}
    for item, rollup in results.items():
        rolledup_category = demand_calculation_config.rollup_fn(item)
        if not rolledup_category in rollup_results:
            rollup_results[rolledup_category] = AssetRollup(
                asset=rolledup_category, total_cols=supply_cols
            )
        rollup_results[rolledup_category] += rollup

    return rollup_results


def deliveries_for_period(time_start: datetime, time_end: datetime):
    """
    Returns
    :param time_start:
    :param time_end:
    :param rollup_fn:
    :return: dict of rolledup item name -> demand over the period
    """
    demand_by_day = (
        FacilityDelivery.active()
        .filter(date__gte=time_start, date__lte=time_end)
        .values("item")
        .annotate(Sum("quantity"))
    )
    rollup = collections.defaultdict(lambda: 0)
    for row in demand_by_day:
        rollup[row["item"]] += row["quantity__sum"]
    return rollup


def known_recent_demand() -> Dict[dc.Item, Demand]:
    recent_demands = {}
    # TODO replace with `max by item`
    for demand in Demand.active():
        # Only use the most recent demand record
        if demand.item in recent_demands:
            prev_demand = recent_demands[demand.item]
            if demand.start_date > prev_demand.start_date:
                recent_demands[demand.item] = demand
        else:
            recent_demands[demand.item] = demand

    return recent_demands


def compute_scaling_factor(
    past_period: Period,
    projection_period: Period,
    demand_calculation_config: DemandCalculationConfig,
) -> float:
    if demand_calculation_config.use_hospitalization_projection:
        # Get last week'ks total hospitalization
        past_period_hospitalization = get_total_hospitalization(
            past_period.start, past_period.end
        )
        projection_period_hospitalization = get_total_hospitalization(
            projection_period.start, projection_period.end
        )
        return projection_period_hospitalization / past_period_hospitalization
    else:
        return projection_period.inclusive_length() / past_period.inclusive_length()


def add_demand_estimate(
    time_start: datetime,
    time_end: datetime,
    asset_rollup: Dict[dc.Item, AssetRollup],
    demand_calculation_config: DemandCalculationConfig,
):
    last_week_start = datetime.datetime.today() - datetime.timedelta(days=7)
    last_week_end = last_week_start + datetime.timedelta(days=6)

    # Get last week's deliveries
    last_weeks_deliveries = deliveries_for_period(last_week_start, last_week_end)
    real_demand = known_recent_demand()

    for k, asset_rollup in asset_rollup.items():
        # Start with by computing a fallback based on delivery data
        asset_deliveries = last_weeks_deliveries.get(k)
        if asset_deliveries is not None:
            asset_rollup.demand = int(
                asset_deliveries
                * compute_scaling_factor(
                    past_period=Period(last_week_start, last_week_end),
                    projection_period=Period(time_start, time_end),
                    demand_calculation_config=demand_calculation_config,
                )
            )
            asset_rollup.demand_src = {DemandSrc.past_deliveries}

        # If desired & it exists, compute a calculation based on actual demand
        if demand_calculation_config.use_real_demand:
            demand_for_asset = real_demand.get(k)
            if demand_for_asset is not None:
                scaling_factor = compute_scaling_factor(
                    past_period=Period(
                        demand_for_asset.start_date, demand_for_asset.end_date
                    ),
                    projection_period=Period(time_start, time_end),
                    demand_calculation_config=demand_calculation_config,
                )
                asset_rollup.demand = int(demand_for_asset.demand * scaling_factor)
                asset_rollup.demand_src = {DemandSrc.real_demand}


def get_total_hospitalization(time_start: datetime, time_end: datetime) -> float:
    total_hospitalization = 0
    date = time_start
    while date <= time_end:
        hospitalization = HOSPITALIZATION.get(date.strftime("%Y-%m-%d"))
        # Use All Beds Available (max during normal operation, not theoretical upper bounds) as lower bound
        if not hospitalization or hospitalization < ALL_BEDS_AVAILABLE:
            hospitalization = ALL_BEDS_AVAILABLE
        total_hospitalization += hospitalization
        date += datetime.timedelta(days=1)

    return total_hospitalization


def pretty_render_numeric(value):
    (value, unit) = split_value_unit(value)
    return format_html(
        '<span class="value">{}</span><span class="unit">{}</span>', value, unit
    )


def split_value_unit(value):
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}", "M"
    elif abs(value) >= 1_000:
        if value % 1000 == 0:
            return value // 1000, "K"
        else:
            return f"{value / 1_000:.1f}", "K"
    else:
        return str(value), ""


class NumericalColumn(tables.Column):
    def render(self, value):
        if value == 0:
            return "—"
        else:
            return pretty_render_numeric(value)

    def render_footer(self, bound_column, table):
        if table.has_footer:
            return pretty_render_numeric(
                sum(bound_column.accessor.resolve(row) for row in table.data)
            )


class AggregationTable(tables.Table):
    has_footer = False
    asset = tables.Column(footer="Total")
    projected_demand = NumericalColumn(
        accessor="demand",
        verbose_name="Demand Proxy",
        attrs={
            "th": {"class": "tooltip", "aria-label": DEMAND_MESSAGE},
            "td": {
                "class": "tooltip",
                "aria-label": lambda record: record.demand_src_display(),
            },
        },
    )
    balance = tables.Column(
        empty_values=(),
        order_by="percent_balance",
        attrs={
            "th": {
                "class": "tooltip",
                "aria-label": "Supply deficit or surplus against demand",
            }
        },
    )

    total = NumericalColumn(
        verbose_name="Supply",
        attrs={
            "th": {
                "class": "tooltip supply-col",
                "aria-label": "Sum of inventory, ordered, and made.",
            }
        },
    )
    inventory = NumericalColumn(
        attrs={
            "th": {
                "class": "tooltip",
                "aria-label": lambda: f"DOHMH [{Inventory.as_of_latest()}]",
                "data-supply-col": lambda bound_column: bound_column.name,
            },
            "td": {
                "data-supply-col": lambda bound_column: bound_column.name,
            },
        }
    )
    donated = NumericalColumn(
        verbose_name="Donated",
        attrs={
            "th": {
                "class": "tooltip",
                "aria-label": lambda: f"DCAS pending pledges [{current_as_of(Purchase.active().filter(order_type=dc.OrderType.Donation))}]",
                "data-supply-col": lambda bound_column: bound_column.name,
            },
            "td": {
                "data-supply-col": lambda bound_column: bound_column.name,
            }
        },
    )
    ordered = NumericalColumn(
        verbose_name="Ordered",
        attrs={
            "th": {
                "class": "tooltip",
                "aria-label": lambda: f"DCAS scheduled orders [{current_as_of(Purchase.active().filter(order_type=dc.OrderType.Purchase))}]",
                "data-supply-col": lambda bound_column: bound_column.name,
            },
            "td": {
                "data-supply-col": lambda bound_column: bound_column.name,
            },
        },
    )

    made = NumericalColumn(
        verbose_name="Made",
        attrs={
            "th": {
                "class": "tooltip",
                "aria-label": lambda: f"EDC scheduled deliveries [{current_as_of(Purchase.active().filter(order_type=dc.OrderType.Make))}]",
                "data-supply-col": lambda bound_column: bound_column.name,
            },
            "td": {
                "data-supply-col": lambda bound_column: bound_column.name,
            },
        },
    )

    def render_projected_demand(self, value):
        if value == 0:
            return pretty_render_numeric(value)
        return format_html(
            '<span class="value-divider">~ </span>{}'.format(
                pretty_render_numeric(value)
            )
        )

    def render_asset(self, value):
        params = {"category": value.value, **self.request.GET}
        if isinstance(value, dc.MayoralCategory):
            params["rollup"] = "mayoral"
        param_str = urlencode(params, doseq=True)
        base_url = reverse("drilldown")
        return format_html(
            '<a href="{base_url}?{param_str}">{display_name}',
            base_url=base_url,
            param_str=mark_safe(param_str),
            display_name=value.display(),
        )

    def render_balance(self, record: AssetRollup):
        absolute = record.absolute_balance
        percent = record.percent_balance
        value, unit = split_value_unit(absolute)
        percent_str = f"{int(percent * 100)}"
        if percent * 100 > 500:
            percent_str = ">500"
        color_class = ""
        if percent < -0.2:
            color_class = "red"
        elif percent < 0:
            color_class = "yellow"
        else:
            color_class = "gray"

        # for some reason the whitespace keeps showing up in the HTML
        # so confused.
        return format_html(
            '<div style="width: 230px; display: flex; justify-content: space-between">'
            "<span>"  # start numeric
            "<span>"
            '<span class="value balance-col {color_class}">{value}</span><span class="unit">{unit}</span>'
            "</span>"
            '&nbsp;<span class="value-divider">/</span>&nbsp;'
            '<span><span class="value {color_class} balance-col">{percent_str}</span><span class="unit">%</span></span>'
            "</span>"
            "</span>"  # end numeric
            "<span >"  # start balance bar
            '<span style="padding-left: {neg_delta}px">'
            '<span class="balance-bar-{color_class}" style="padding-left: {neg_width}px"></span>'
            "</span>"
            '<span class="divider"></span>'
            '<span style="padding-right: {pos_delta}px">'
            '<span class="balance-bar-{color_class}" style="padding-left: {pos_width}px"></span>'
            "</span>"
            "</span>"  # end balance bar
            "</div>",
            color_class=color_class,
            value=value,
            unit=unit,
            percent_str=percent_str,
            neg_width=min(min(int(percent * 50), 0) * -1, 50),
            pos_width=max(min(int(percent * 50), 50), 0),
            neg_delta=50 - min(min(int(percent * 50), 0) * -1, 50),
            pos_delta=50 - max(min(int(percent * 50), 50), 0),
        )

    class Meta:
        order_by = ("balance",)
        sequence = (
            "asset",
            "projected_demand",
            "total",
            "balance",
            "inventory",
            "ordered",
            "made",
            "donated",
        )


class TotaledAggregationTable(AggregationTable):
    has_footer = True
