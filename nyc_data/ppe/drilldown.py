import ppe.dataclasses as dc
from datetime import datetime

from ppe.models import Delivery
from typing import List, Callable


def deliveries_for_item(item_type: str, rollup_fn: Callable[[dc.Item], str]) -> List[Delivery]:
    deliveries = Delivery.active().prefetch_related('purchase').filter(delivery_date__gte=datetime.utcnow()).order_by('delivery_date')
    return [d for d in deliveries if rollup_fn(dc.Item(d.purchase.item)) == item_type]
