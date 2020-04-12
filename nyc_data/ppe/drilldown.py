import ppe.dataclasses as dc
from datetime import datetime

from ppe.models import Delivery, Purchase
from typing import List, Callable, NamedTuple


class DrilldownResult(NamedTuple):
    purchases: List[Purchase]

def drilldown_result(item_type: str, rollup_fn: Callable[[dc.Item], str]):
    # could do this in SQL but probably unecessary
    purchases = Purchase.active().prefetch_related('deliveries')
    purchases = [p for p in purchases if rollup_fn(dc.Item(p.item)) == item_type]
    return purchases


