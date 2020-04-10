import datetime
from dataclasses import dataclass
from typing import Dict, List, Callable

import django_tables2 as tables
from django.utils.html import format_html

from ppe.models import Delivery
import ppe.dataclasses as dc


@dataclass
class AssetRollup:
    asset: str
    demand: int = 0
    donate: int = 0
    sell: int = 0
    make: int = 0

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
    relevant_deliveries = Delivery.objects.prefetch_related("purchase").filter(
        delivery_date__gte=time_start, delivery_date__lte=time_end, replaced=False
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
    if estimate_demand:
        add_demand_estimate(time_start, time_end, results, rollup_fn)

    return results


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
    projected_demand = NumericalColumn(accessor="demand")
    balance = tables.Column(empty_values=(), order_by="percent_balance")

    total = NumericalColumn()
    donate = NumericalColumn()
    sell = NumericalColumn()
    make = NumericalColumn()

    def render_asset(self, value):
        return value.display()

    def render_balance(self, record: AssetRollup):
        absolute = record.absolute_balance
        percent = record.percent_balance
        value, unit = split_value_unit(absolute)
        percent_str = f'{int(percent * 100)}'
        color_class = ''
        if percent < -.2:
            color_class = 'red'
        elif percent < 0:
            color_class = 'yellow'

        return format_html(
            '<span class="balance-absolute">'
            '<span class="value {}">{}</span><span class="unit">{}</span>'
            '</span>'
            '&nbsp;/&nbsp'
            '<span class="value {}">{}</span>%',
            color_class,
            value,

            unit,
            color_class,
            percent_str
        )

    class Meta:
        pass
