import ppe.dataclasses as dc
from datetime import datetime, timedelta, date

from ppe import aggregations
from ppe.aggregations import AssetRollup, DemandCalculationConfig
from ppe.models import ScheduledDelivery, Purchase, Inventory
from ppe.dataclasses import OrderType
from typing import List, Callable, NamedTuple, Dict

from ppe.utils import log_db_queries


class DrilldownResult(NamedTuple):
    purchases: List[Purchase]
    scheduled_deliveries: List[ScheduledDelivery]
    inventory: List[Inventory]
    donations: List[Purchase]
    aggregation: Dict[str, AssetRollup]


@log_db_queries
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

    donations = [
        d
        for d in purchases if rollup_fn(dc.Item(d.item)) == item_type and d.order_type == OrderType.Donation and not d.complete
    ]

    for don in donations:
        days_since_pledge =  (date.today() - don.donation_date).days
        if days_since_pledge >= 7:
            pledge_status = "error"
        elif days_since_pledge > 3:
            pledge_status = "warning"
        else:
            pledge_status = "pending" 
        setattr(don, "pledge_status", pledge_status)
        setattr(don, "days_since_pledge", days_since_pledge)

    purchases = [
        p
        for p in purchases
        if rollup_fn(dc.Item(p.item)) == item_type and not p.complete and p.order_type != OrderType.Donation
    ]

    deliveries = [list(p.deliveries.all()) for p in purchases]
    # flatten
    deliveries = sum(deliveries, [])
    deliveries = sorted(deliveries, key=lambda d: d.delivery_date)
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
        purchases, deliveries, inventory, donations, aggregation=filtered_aggregation
    )
