import ppe.dataclasses as dc
from datetime import datetime, timedelta

from ppe import aggregations
from ppe.aggregations import AssetRollup, DemandCalculationConfig
from ppe.models import ScheduledDelivery, Purchase, Inventory
from typing import List, Callable, NamedTuple, Dict


class DrilldownResult(NamedTuple):
    purchases: List[Purchase]
    scheduled_deliveries: List[ScheduledDelivery]
    inventory: List[Inventory]
    aggregation: Dict[str, AssetRollup]


def drilldown_result(
    item_type: str, rollup_fn: Callable[[dc.Item], str], time_range: dc.Period = None
):
    # could do this in SQL but probably unecessary
    if time_range is None:
        time_range = dc.Period(datetime.today(), datetime.today() + timedelta(days=30))
    purchases = (
        Purchase.active()
        .prefetch_related("deliveries")
        .order_by("deliveries__delivery_date")
    )
    purchases = [p for p in purchases if rollup_fn(dc.Item(p.item)) == item_type]
    deliveries = (
        ScheduledDelivery.active()
        .prefetch_related("purchase")
        .order_by("delivery_date")
    )
    deliveries = [d for d in deliveries if rollup_fn(dc.Item(d.item)) == item_type]
    inventory = [
        i for i in Inventory.active() if rollup_fn(dc.Item(i.item)) == item_type
    ]

    aggregation = aggregations.asset_rollup(
        time_range=time_range, demand_calculation_config=DemandCalculationConfig()
    )
    filtered_aggregation = {
        item: agg for item, agg in aggregation.items() if rollup_fn(item) == item_type
    }
    return DrilldownResult(
        purchases, deliveries, inventory, aggregation=filtered_aggregation
    )
