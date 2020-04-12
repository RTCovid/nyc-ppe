import datetime
from dataclasses import dataclass
from typing import Dict, Callable

import django_tables2 as tables
from django.utils.html import format_html

import ppe.dataclasses as dc
from ppe.models import ScheduledDelivery, Inventory, ImportStatus


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
        estimate_demand=True
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
        add_demand_estimate(time_start, time_end, results, rollup_fn)

    return results

def is_zero():
  return self.donate == 0 and self.sell == 0 and self.make == 0 and self.inventory == 0

def add_demand_estimate(time_start: datetime, time_end: datetime, rollup: Dict[str, AssetRollup], rollup_fn):
    last_week = datetime.datetime.today() - datetime.timedelta(days=7)

    last_week_rollup = asset_rollup(last_week, datetime.datetime.today(), rollup_fn=rollup_fn, estimate_demand=False)
    scaling_factor = (time_end - time_start) / datetime.timedelta(days=7)
    for k, rollup in rollup.items():
        # ignore donations
        last_week_supply = last_week_rollup[k].sell + last_week_rollup[k].make
        rollup.demand = int(last_week_supply * scaling_factor)


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
    projected_demand = NumericalColumn(accessor="demand", verbose_name="Demand")
    balance = tables.Column(empty_values=(), order_by="percent_balance")

    total = NumericalColumn(verbose_name="Supply")
    inventory = NumericalColumn(attrs={"th": {"class": "tooltip", "aria-label": lambda: f"MO Operations current as of {Inventory.as_of_latest()}"}})
    donate = NumericalColumn()
    sell = NumericalColumn(attrs={"th": {"class": "tooltip", "aria-label": "DCAS"}})
    make = NumericalColumn(attrs={"th": {"class": "tooltip", "aria-label": "EDC"}})

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
            'sell',
            'make',
        )
        exclude = (
            'donate',
        )
