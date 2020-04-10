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
            datetime.now() - timedelta(days=30), datetime.now()
        )
        self.assertEqual(len(rollup), 15)
        self.assertEqual(rollup[dc.Item.gown], AssetRollup(asset=dc.Item.gown, sell=5))

        future_rollup = aggregations.asset_rollup(
            datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=30)
        )
        self.assertEqual(
            future_rollup[dc.Item.gown], AssetRollup(asset=dc.Item.gown, sell=1005)
        )


class TestCategoryMappings(unittest.TestCase):
    def test_category_to_mayoral(self):
        for _, item in dc.Item.__members__.items():
            self.assertIn(item, dc.ITEM_TO_MAYORAL)
