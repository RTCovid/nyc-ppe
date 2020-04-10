import datetime
from dataclasses import dataclass
from typing import Dict, List, Callable

import django_tables2 as tables

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


MAPPING = {dc.OrderType.Make: "make", dc.OrderType.Purchase: "sell"}


def asset_rollup(
        time_start: datetime,
        time_end: datetime,
        asset_rollup: Callable[[dc.Item], str] = lambda x: x,
) -> Dict[str, AssetRollup]:
    relevant_deliveries = Delivery.objects.prefetch_related("purchase").filter(
        delivery_date__gte=time_start, delivery_date__lte=time_end, replaced=False
    )

    results: Dict[str, AssetRollup] = {}
    for _, item in dc.Item.__members__.items():
        results[asset_rollup(item)] = AssetRollup(asset=asset_rollup(item))

    for delivery in relevant_deliveries:
        rollup = results[asset_rollup(dc.Item(delivery.purchase.item))]
        tpe = delivery.purchase.order_type
        param = MAPPING.get(tpe)
        if param is None:
            raise Exception(f"unexpected purchase type: `{tpe}`")
        setattr(rollup, param, getattr(rollup, param) + delivery.quantity)

    return results


class AggregationTable(tables.Table):
    asset = tables.Column()
    demand = tables.Column()
    total = tables.Column()
    donate = tables.Column()
    sell = tables.Column()
    make = tables.Column()

    def render_asset(self, value):
        return value.display()

    class Meta:
        template_name = "django_tables2/bootstrap4.html"
