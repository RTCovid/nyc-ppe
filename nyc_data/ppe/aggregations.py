import collections
import datetime
from dataclasses import dataclass
from typing import Dict, Callable
import json

import django_tables2 as tables
from django.db.models import Sum
from django.utils.html import format_html

import ppe.dataclasses as dc
from ppe.models import ScheduledDelivery, Inventory, ImportStatus, FacilityDelivery, WeeklyDemand

# NY Forecast from https://covid19.healthdata.org/united-states-of-america/new-york
HOSPITALIZATION = {}
with open('../public-data/hospitalization_projection_new_york.json', 'r') as f:
    HOSPITALIZATION = json.load(f)
ALL_BEDS_AVAILABLE = 20420


@dataclass
class AssetRollup:
    asset: str
    demand: int = 0
    donate: int = 0
    sell: int = 0
    make: int = 0
    inventory: int = 0

    @property
    def total(self):
        return self.donate + self.sell + self.make + self.inventory

    @property
    def absolute_balance(self):
        return self.total - self.demand

    @property
    def percent_balance(self):
        return self.absolute_balance / (self.demand + 1)


MAPPING = {dc.OrderType.Make: "make", dc.OrderType.Purchase: "sell"}


def asset_rollup(
        time_start: datetime,
        time_end: datetime,
        rollup_fn: Callable[[dc.Item], any] = lambda x: x,
        estimate_demand=True,
        use_hospitalization_projection=True,
        use_delivery_as_demand=True,
) -> Dict[str, AssetRollup]:
    relevant_deliveries = ScheduledDelivery.active().prefetch_related('purchase').filter(
        delivery_date__gte=time_start, delivery_date__lte=time_end
    )

    results: Dict[str, AssetRollup] = {}
    for _, item in dc.Item.__members__.items():
        results[rollup_fn(item)] = AssetRollup(asset=rollup_fn(item))

    for delivery in relevant_deliveries:
        rollup = results[rollup_fn(dc.Item(delivery.purchase.item))]
        tpe = delivery.purchase.order_type
        param = MAPPING.get(tpe)
        if param is None:
            raise Exception(f"unexpected purchase type: `{tpe}`")
        setattr(rollup, param, getattr(rollup, param) + delivery.quantity)

    inventory = Inventory.active()
    for item in inventory:
        rollup = results[rollup_fn(dc.Item(item.item))]
        rollup.inventory += item.quantity

    if estimate_demand:
        add_demand_estimate(time_start, time_end, results, rollup_fn, use_hospitalization_projection,
                            use_delivery_demand=use_delivery_as_demand)

    return results


def demand_for_period(time_start: datetime, time_end: datetime, rollup_fn):
    """
    Returns
    :param time_start:
    :param time_end:
    :param rollup_fn:
    :return: dict of rolledup item name -> demand over the period
    """
    demand_by_day = FacilityDelivery.active().filter(date__gte=time_start, date__lte=time_end).values('item').annotate(
        Sum('quantity'))
    rollup = collections.defaultdict(lambda: 0)
    for row in demand_by_day:
        rollup[rollup_fn(dc.Item(row['item']))] += row['quantity__sum']
    return rollup


def known_recent_demand():

    recent_demands = {}
    for weeklyDemand in WeeklyDemand.active():
        # Only use the most recent demand record
        if weeklyDemand.item in recent_demands:
            prev_demand = recent_demands[weeklyDemand.item]
            if weeklyDemand.week_start_date > prev_demand.week_start_date:
                recent_demands[weeklyDemand.item] = weeklyDemand
        else:
            recent_demands[weeklyDemand.item] = weeklyDemand

    return recent_demands


def add_demand_estimate(time_start: datetime,
                        time_end: datetime,
                        rollup: Dict[str, AssetRollup],
                        rollup_fn,
                        use_hospitalization_projection=True,
                        use_delivery_demand=False):

    last_week_start = datetime.datetime.today() - datetime.timedelta(days=7)
    last_week_end = last_week_start+datetime.timedelta(days=6)

    # Get last week's demands
    last_weeks_demand = get_total_demands(last_week_start, last_week_end, rollup_fn, use_delivery_demand)

    # Calculate scaling factor (both time_start and time_end are inclusive)
    scaling_factor = (time_end - time_start + datetime.timedelta(days=1)) / datetime.timedelta(days=7)

    # Get last week's total hospitalization
    last_week_hospitalization = get_total_hospitalization(last_week_start, last_week_end)

    recent_demands = known_recent_demand()
    # Iterate through each category
    for k, rollup in rollup.items():
        # ignore donations
        last_week_supply = last_weeks_demand[k]
        if use_hospitalization_projection:
            # Per hospitalization demand
            demand_per_patient_per_day = last_week_supply / last_week_hospitalization
            # Recalculate the value if we have true demand data for the category
            if k in recent_demands:
                recent_demand = recent_demands[k]
                hospitalization_of_the_week = get_total_hospitalization(recent_demand.week_start_date,
                                                                        recent_demand.week_end_date)
                demand_per_patient_per_day = recent_demand.demand / hospitalization_of_the_week

            # Add up the forecast demand for each day between time_start and time_end
            projected_demand = get_projected_demand(time_start, time_end, demand_per_patient_per_day)
            rollup.demand = int(sum(projected_demand))
        else:
            rollup.demand = int(last_week_supply * scaling_factor)


def get_projected_demand(time_start: datetime,
                         time_end: datetime,
                         demand_per_patient_per_day):

    projected_demand = []

    date = time_start
    while date <= time_end:
        hospitalization = HOSPITALIZATION[date.strftime("%Y-%m-%d")]
        # Use All Beds Available (max during normal operation, not theoretical upper bounds) as lower bound
        # to make sure that our projection won't fall to zero as the estimated COVID-19
        # related hospitalization falls to zero.
        # We will need to revise this approximation as the hospitalization falls below the Max
        if not hospitalization or hospitalization < ALL_BEDS_AVAILABLE:
            hospitalization = ALL_BEDS_AVAILABLE
        projected_demand.append(demand_per_patient_per_day * hospitalization)
        date += datetime.timedelta(days=1)

    return projected_demand


def get_total_demands(time_start: datetime,
                      time_end: datetime,
                      rollup_fn,
                      use_delivery_demand=False):

    if use_delivery_demand:
        total_demands = demand_for_period(time_start, time_end, rollup_fn)
    else:
        last_week_rollup = asset_rollup(time_start, time_end, rollup_fn, estimate_demand=False)
        total_demands = {k: v.sell + v.make for k, v in last_week_rollup.items()}

    return total_demands


def get_total_hospitalization(time_start: datetime,
                              time_end: datetime):

    total_hospitalization = 0
    date = time_start
    while date <= time_end:
        hospitalization = HOSPITALIZATION[date.strftime("%Y-%m-%d")]
        # Use All Beds Available (max during normal operation, not theoretical upper bounds) as lower bound
        if not hospitalization or hospitalization < ALL_BEDS_AVAILABLE:
            hospitalization = ALL_BEDS_AVAILABLE
        total_hospitalization += hospitalization
        date += datetime.timedelta(days=1)

    return total_hospitalization


def pretty_render_numeric(value):
    (value, unit) = split_value_unit(value)
    return format_html('<span class="value">{}</span><span class="unit">{}</span>', value, unit)


def split_value_unit(value):
    if abs(value) >= 1_000_000:
        return f'{value / 1_000_000:.1f}', 'M'
    elif abs(value) >= 1_000:
        if value % 1000 == 0:
            return value // 1000, 'K'
        else:
            return f'{value / 1_000:.1f}', 'K'
    else:
        return str(value), ''


class NumericalColumn(tables.Column):
    def render(self, value):
        return pretty_render_numeric(value)


class AggregationTable(tables.Table):
    asset = tables.Column()
    projected_demand = NumericalColumn(accessor="demand", verbose_name="Demand Proxy", attrs={"th": {"class": "tooltip", "aria-label": "Demand projected based on the previous 7 days of hospital deliveries & IMHE hospitalization model"}})
    balance = tables.Column(empty_values=(), order_by="percent_balance", attrs={"th": {"class": "tooltip", "aria-label": "Supply deficit or surplus against demand"}})

    total = NumericalColumn(verbose_name="Supply", attrs={"th": {"class": "tooltip", "aria-label": "Sum of inventory, ordered, and made."}})
    inventory = NumericalColumn(attrs={
        "th": {"class": "tooltip", "aria-label": lambda: f"DOHMH [{Inventory.as_of_latest()}]"}})
    donate = NumericalColumn()
    sell = NumericalColumn(verbose_name="Ordered", attrs={"th": {"class": "tooltip", "aria-label": "DCAS scheduled orders [2020-4-12]"}})
    make = NumericalColumn(verbose_name="Made", attrs={"th": {"class": "tooltip", "aria-label": "EDC scheduled deliveries [2020-4-7]"}})

    def render_projected_demand(self, value):
        if value == 0:
            return pretty_render_numeric(value)
        return format_html('<span class="value-divider">~ </span>{}'.format(pretty_render_numeric(value)))

    def render_asset(self, value):
        href = f'/drilldown?category={value}'
        if isinstance(value, dc.MayoralCategory):
            href += '&rollup=mayoral'
        return format_html('<a href="{href}">{display_name}', href=href, display_name=value.display())

    def render_balance(self, record: AssetRollup):
        absolute = record.absolute_balance
        percent = record.percent_balance
        value, unit = split_value_unit(absolute)
        percent_str = f'{int(percent * 100)}'
        if percent * 100 > 500:
            percent_str = '>500'
        color_class = ''
        if percent < -.2:
            color_class = 'red'
        elif percent < 0:
            color_class = 'yellow'
        else:
            color_class = 'gray'

        # for some reason the whitespace keeps showing up in the HTML
        # so confused.
        return format_html(
            '<div style="width: 230px; display: flex; justify-content: space-between">'
            '<span>'  # start numeric
            '<span>'
            '<span class="value balance-col {color_class}">{value}</span><span class="unit">{unit}</span>'
            '</span>'
            '&nbsp;<span class="value-divider">/</span>&nbsp;'
            '<span><span class="value {color_class} balance-col">{percent_str}</span><span class="unit">%</span></span>'
            '</span>'
            '</span>'  # end numeric
            '<span >'  # start balance bar
            '<span style="padding-left: {neg_delta}px">'
            '<span class="balance-bar-{color_class}" style="padding-left: {neg_width}px"></span>'
            '</span>'
            '<span class="divider"></span>'
            '<span style="padding-right: {pos_delta}px">'
            '<span class="balance-bar-{color_class}" style="padding-left: {pos_width}px"></span>'
            '</span>'
            '</span>'  # end balance bar
            '</div>',

            color_class=color_class,
            value=value,

            unit=unit,
            percent_str=percent_str,
            neg_width=min(min(int(percent * 50), 0) * -1, 50),
            pos_width=max(min(int(percent * 50), 50), 0),
            neg_delta=50 - min(min(int(percent * 50), 0) * -1, 50),
            pos_delta=50 - max(min(int(percent * 50), 50), 0),
        )

        # """
        # <span>
        #    <span class="value balance-col {color_class}">{value}</span><span class="unit">{unit}</span>
        #    <span>&nbsp;<span class="value-divider">/</span>&nbsp;</span>
        #    <span>
        #        <span class="value {color_class} balance-col">{percent}</span><span class="unit">%</span>
        #    </span>
        # </span>
        # """

    class Meta:
        order_by = ('balance',)
        sequence = (
            'asset',
            'projected_demand',
            'total',
            'balance',
            'inventory',
            'sell',
            'make',
        )
        exclude = (
            'donate',
        )
