import unittest
from datetime import datetime, timedelta

from django.test import TestCase

from ppe import aggregations
from ppe.aggregations import AssetRollup
from ppe.data_mappings import SourcingRow
import ppe.dataclasses as dc


class TestAssetRollup(TestCase):
    def setUp(self) -> None:
        items = SourcingRow(
            item=dc.Item.gown,
            quantity=1005,
            vendor="Gown Sellers Ltd",
            delivery_day_1=datetime.now() - timedelta(days=5),
            delivery_day_1_quantity=5,
            delivery_day_2=datetime.now() + timedelta(days=1),
            delivery_day_2_quantity=1000,
            raw_data={},
        ).to_objects()

        for item in items:
            item.save()

    def test_rollup(self):
        rollup = aggregations.asset_rollup(
            datetime.now() - timedelta(days=28), datetime.now()
        )
        self.assertEqual(len(rollup), len(dc.Item))
        # demand of 20 = 5 in the last week * 4 weeks in the period
        self.assertEqual(rollup[dc.Item.gown], AssetRollup(asset=dc.Item.gown, demand=20, sell=5))

        future_rollup = aggregations.asset_rollup(
            datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=30)
        )
        self.assertEqual(
            future_rollup[dc.Item.gown], AssetRollup(asset=dc.Item.gown, demand=42, sell=1005)
        )

    def test_mayoral_rollup(self):
        rollup = aggregations.asset_rollup(
            datetime.now() - timedelta(days=28), datetime.now(),
            rollup_fn=lambda row: row.to_mayoral_category()
        )
        # no uncategorized items in the rollup
        self.assertEqual(len(rollup), len(dc.MayoralCategory) - 1)
        self.assertEqual(rollup[dc.MayoralCategory.iso_gowns],
                         AssetRollup(asset=dc.MayoralCategory.iso_gowns, demand=20, sell=5))


class TestCategoryMappings(unittest.TestCase):
    def test_category_to_mayoral(self):
        for _, item in dc.Item.__members__.items():
            self.assertNotEqual(dc.ITEM_TO_MAYORAL.get(item), None, f"No mayoral category defined for {item}")

    def test_display_names(self):
        for _, item in dc.Item.__members__.items():
            self.assertNotEqual(dc.ITEM_TO_DISPLAYNAME.get(item), None, f"No display name defined for {item}")
