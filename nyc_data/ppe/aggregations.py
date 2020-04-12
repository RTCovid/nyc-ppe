import datetime
from dataclasses import dataclass
from typing import Dict, Callable

import django_tables2 as tables
from django.utils.html import format_html

import ppe.dataclasses as dc
from ppe.models import Delivery, Inventory, ImportStatus

# NY Forecast from https://covid19.healthdata.org/united-states-of-america/new-york
ALL_BEDS_AVAILABLE = 13010
HOSPITALIZATION = {
    "2020-03-09": 9,
    "2020-03-10": 13,
    "2020-03-11": 44,
    "2020-03-12": 58,
    "2020-03-13": 71,
    "2020-03-14": 151,
    "2020-03-15": 185,
    "2020-03-16": 257,
    "2020-03-17": 502,
    "2020-03-18": 661,
    "2020-03-19": 880,
    "2020-03-20": 1187,
    "2020-03-21": 1570,
    "2020-03-22": 2160,
    "2020-03-23": 2947,
    "2020-03-24": 3780,
    "2020-03-25": 4726,
    "2020-03-26": 5962,
    "2020-03-27": 7367,
    "2020-03-28": 8831,
    "2020-03-29": 10679,
    "2020-03-30": 12606,
    "2020-03-31": 14234,
    "2020-04-01": 15486,
    "2020-04-02": 17554,
    "2020-04-03": 19331,
    "2020-04-04": 20937,
    "2020-04-05": 21937,
    "2020-04-06": 22492,
    "2020-04-07": 23069,
    "2020-04-08": 23362,
    "2020-04-09": 22602,
    "2020-04-10": 21586,
    "2020-04-11": 20246,
    "2020-04-12": 18751,
    "2020-04-13": 17198,
    "2020-04-14": 15551,
    "2020-04-15": 13868,
    "2020-04-16": 12198,
    "2020-04-17": 10596,
    "2020-04-18": 9085,
    "2020-04-19": 7700,
    "2020-04-20": 6476,
    "2020-04-21": 5420,
    "2020-04-22": 4457,
    "2020-04-23": 3642,
    "2020-04-24": 2952,
    "2020-04-25": 2376,
    "2020-04-26": 1905,
    "2020-04-27": 1517,
    "2020-04-28": 1200,
    "2020-04-29": 944,
    "2020-04-30": 738,
    "2020-05-01": 573,
    "2020-05-02": 441,
    "2020-05-03": 335,
    "2020-05-04": 252,
    "2020-05-05": 187,
    "2020-05-06": 138,
    "2020-05-07": 100,
    "2020-05-08": 71,
    "2020-05-09": 50,
    "2020-05-10": 35,
    "2020-05-11": 25,
    "2020-05-12": 17,
    "2020-05-13": 11,
    "2020-05-14": 8,
    "2020-05-15": 5,
    "2020-05-16": 3,
    "2020-05-17": 2,
    "2020-05-18": 1,
    "2020-05-19": 1,
    "2020-05-20": 0,
    "2020-05-21": 0,
    "2020-05-22": 0,
    "2020-05-23": 0,
    "2020-05-24": 0,
    "2020-05-25": 0,
    "2020-05-26": 0,
    "2020-05-27": 0,
    "2020-05-28": 0,
    "2020-05-29": 0,
    "2020-05-30": 0,
    "2020-05-31": 0,
    "2020-06-01": 0,
    "2020-06-02": 0,
    "2020-06-03": 0,
    "2020-06-04": 0,
    "2020-06-05": 0,
    "2020-06-06": 0,
    "2020-06-07": 0,
    "2020-06-08": 0,
    "2020-06-09": 0,
    "2020-06-10": 0,
    "2020-06-11": 0,
    "2020-06-12": 0,
    "2020-06-13": 0,
    "2020-06-14": 0,
    "2020-06-15": 0,
    "2020-06-16": 0,
    "2020-06-17": 0,
    "2020-06-18": 0,
    "2020-06-19": 0,
    "2020-06-20": 0,
    "2020-06-21": 0,
    "2020-06-22": 0,
    "2020-06-23": 0,
    "2020-06-24": 0,
    "2020-06-25": 0,
    "2020-06-26": 0,
    "2020-06-27": 0,
    "2020-06-28": 0,
    "2020-06-29": 0,
    "2020-06-30": 0,
    "2020-07-01": 0,
    "2020-07-02": 0,
    "2020-07-03": 0,
    "2020-07-04": 0,
    "2020-07-05": 0,
    "2020-07-06": 0,
    "2020-07-07": 0,
    "2020-07-08": 0,
    "2020-07-09": 0,
    "2020-07-10": 0,
    "2020-07-11": 0,
    "2020-07-12": 0,
    "2020-07-13": 0,
    "2020-07-14": 0,
    "2020-07-15": 0,
    "2020-07-16": 0,
    "2020-07-17": 0,
    "2020-07-18": 0,
    "2020-07-19": 0,
    "2020-07-20": 0,
    "2020-07-21": 0,
    "2020-07-22": 0,
    "2020-07-23": 0,
    "2020-07-24": 0,
    "2020-07-25": 0,
    "2020-07-26": 0,
    "2020-07-27": 0,
    "2020-07-28": 0,
    "2020-07-29": 0,
    "2020-07-30": 0,
    "2020-07-31": 0,
    "2020-08-01": 0,
    "2020-08-02": 0,
    "2020-08-03": 0,
    "2020-08-04": 0
}


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
        return self.donate + self.sell + self.make

    @property
    def absolute_balance(self):
        return self.total - self.demand

    @property
    def percent_balance(self):
        return self.total / (self.demand + 1) * (-1 if self.absolute_balance < 0 else 1)


MAPPING = {dc.OrderType.Make: "make", dc.OrderType.Purchase: "sell"}


def asset_rollup(
        time_start: datetime,
        time_end: datetime,
        rollup_fn: Callable[[dc.Item], any] = lambda x: x,
        estimate_demand=True
) -> Dict[str, AssetRollup]:
    relevant_deliveries = Delivery.objects.prefetch_related("purchase", "source").filter(
        delivery_date__gte=time_start, delivery_date__lte=time_end, source__status=ImportStatus.active
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

    inventory = Inventory.objects.prefetch_related("source").filter(source__status=ImportStatus.active)
    for item in inventory:
        rollup = results[rollup_fn(dc.Item(item.item))]
        rollup.inventory += item.quantity

    if estimate_demand:
        add_demand_estimate(time_start, time_end, results, rollup_fn)

    return results


def add_demand_estimate(time_start: datetime, time_end: datetime, rollup: Dict[str, AssetRollup], rollup_fn):
    last_week = datetime.datetime.today() - datetime.timedelta(days=7)
    last_week_rollup = asset_rollup(last_week, datetime.datetime.today(), rollup_fn=rollup_fn, estimate_demand=False)

    # Get last week's total hospitalization
    total_hospitalization = 0
    for n in range(0, 6):
        date = last_week + datetime.timedelta(days=n)
        hospitalization = HOSPITALIZATION[date.strftime("%Y-%m-%d")]
        # Use All Beds Available as baseline
        if not hospitalization or hospitalization < ALL_BEDS_AVAILABLE:
            hospitalization = ALL_BEDS_AVAILABLE
        total_hospitalization += hospitalization

    # Iterate through each category
    for k, rollup in rollup.items():
        # ignore donations
        last_week_supply = last_week_rollup[k].sell + last_week_rollup[k].make

        # Per hospitalization demand
        demand_per_patient_per_day = last_week_supply / total_hospitalization

        # Add up the forecast demand for each day between time_start and time_end
        rollup.demand = 0
        date = time_start
        while date <= time_end:
            hospitalization = HOSPITALIZATION[date.strftime("%Y-%m-%d")]
            if not hospitalization or hospitalization < ALL_BEDS_AVAILABLE:
                hospitalization = ALL_BEDS_AVAILABLE
            rollup.demand += demand_per_patient_per_day * hospitalization
            date += datetime.timedelta(days=1)


def pretty_render_numeric(value):
    (value, unit) = split_value_unit(value)
    return format_html('<span class="value">{}</span><span class="unit">{}</span>', value, unit)


def split_value_unit(value):
    if abs(value) > 1_000_000:
        return f'{value / 1_000_000:.1f}', 'M'
    elif abs(value) > 1_000:
        return f'{value / 1_000:.1f}', 'K'
    else:
        return value, ''


class NumericalColumn(tables.Column):
    def render(self, value):
        return pretty_render_numeric(value)


class AggregationTable(tables.Table):
    asset = tables.Column()
    projected_demand = NumericalColumn(accessor="demand")
    balance = tables.Column(empty_values=(), order_by="percent_balance")

    total = NumericalColumn()
    inventory = NumericalColumn()
    donate = NumericalColumn()
    sell = NumericalColumn()
    make = NumericalColumn()

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
            neg_width=min(min(int(percent * 100), 0) * -1, 50),
            pos_width=max(min(int(percent * 100), 50), 0),
            neg_delta=50 - min(min(int(percent * 100), 0) * -1, 50),
            pos_delta=50 - max(min(int(percent * 100), 50), 0),
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
            'donate',
            'sell',
            'make',
        )
