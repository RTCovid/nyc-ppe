import datetime
from dataclasses import dataclass
from typing import Dict, List

from ppe.models import Delivery
import ppe.dataclasses as dc


@dataclass
class AssetRollup:
    asset: dc.Item
    demand: int = 0
    donate: int = 0
    sell: int = 0
    make: int = 0


MAPPING = {
    dc.OrderType.Make: 'make',
    dc.OrderType.Purchase: 'sell'
}


def asset_rollup(time_start: datetime, time_end: datetime) -> Dict[dc.Item, AssetRollup]:
    relevant_deliveries = Delivery.objects.prefetch_related('purchase').filter(delivery_date__gte=time_start,
                                                                               delivery_date__lte=time_end)

    results: Dict[dc.Item, AssetRollup] = {}
    for _, item in dc.Item.__members__.items():
        results[item] = AssetRollup(asset=item)

    for delivery in relevant_deliveries:
        print(delivery.__dict__)
        rollup = results[delivery.purchase.item]
        tpe = delivery.purchase.order_type
        param = MAPPING.get(tpe)
        if param is None:
            raise Exception(f'unexpected purchase type: {tpe}')
        setattr(rollup, param, delivery.quantity)

    return results
