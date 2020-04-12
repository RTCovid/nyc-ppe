import ppe.dataclasses as dc
from datetime import datetime

from ppe.models import ScheduledDelivery, Purchase
from typing import List, Callable, NamedTuple


class DrilldownResult(NamedTuple):
    purchases: List[Purchase]

def drilldown_result(item_type: str, rollup_fn: Callable[[dc.Item], str]):
    # could do this in SQL but probably unecessary
    purchases = Purchase.active().prefetch_related('deliveries').order_by('deliveries__delivery_date')
    purchases = [p for p in purchases if rollup_fn(dc.Item(p.item)) == item_type]
    deliveries = ScheduledDelivery.active().prefetch_related('purchase').order_by('delivery_date')
    deliveries = [d for d in deliveries if rollup_fn(dc.Item(d.purchase.item)) == item_type]
    return purchases, deliveries


