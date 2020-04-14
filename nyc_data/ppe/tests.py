import unittest
from datetime import datetime, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse

from ppe import aggregations
from ppe.aggregations import AssetRollup
from ppe.data_mapping.types import DataFile
from ppe.data_mapping.mappers.dcas_sourcing import SourcingRow
from ppe.data_mapping.mappers.hospital_demands import DemandRow
import ppe.dataclasses as dc
from ppe.data_mapping.utils import ErrorCollector
from ppe.models import DataImport, ImportStatus, Purchase


class TestAssetRollup(TestCase):
    def setUp(self) -> None:
        self.data_import = DataImport(
            status=ImportStatus.active,
            data_file=DataFile.PPE_ORDERINGCHARTS_DATE_XLSX,
            file_checksum='123'
        )
        self.data_import.save()
        items = SourcingRow(
            item=dc.Item.gown,
            quantity=1005,
            vendor="Gown Sellers Ltd",
            description='Some gowns',
            delivery_day_1=datetime.strptime('2020-04-12', '%Y-%m-%d') - timedelta(days=5),
            delivery_day_1_quantity=5,
            status='Completed',
            received_quantity=0,
            delivery_day_2=datetime.strptime('2020-04-12', '%Y-%m-%d') + timedelta(days=1),
            delivery_day_2_quantity=1000,
            raw_data={},
        ).to_objects(ErrorCollector())

        for item in items:
            item.source = self.data_import
            item.save()

        items = DemandRow(
            item=dc.Item.gown,
            demand=2457000,
            week_start_date=datetime.strptime('2020-04-11', '%Y-%m-%d'),
            week_end_date=datetime.strptime('2020-04-17', '%Y-%m-%d'),
            raw_data={},
        ).to_objects(ErrorCollector())
        data_import = DataImport(
            status=ImportStatus.active,
            data_file=DataFile.HOSPITAL_DEMANDS,
            file_checksum='123'
        )
        data_import.save()
        for item in items:
            item.source = data_import
            item.save()

    def test_rollup(self):
        today = datetime(2020, 4, 12)
        rollup = aggregations.asset_rollup(
            today - timedelta(days=28), today, use_delivery_as_demand=False
        )
        self.assertEqual(len(rollup), len(dc.Item))
        # demand of 20 = 5 in the last week * 4 weeks in the period
        self.assertEqual(rollup[dc.Item.gown], AssetRollup(asset=dc.Item.gown, demand=7915269, sell=5))

        # Turn of use of hospitalization projection
        rollup = aggregations.asset_rollup(
            today - timedelta(days=28), today,
            use_hospitalization_projection=False,
            use_delivery_as_demand=False
        )
        self.assertEqual(rollup[dc.Item.gown], AssetRollup(asset=dc.Item.gown, demand=4163, sell=5))

        future_rollup = aggregations.asset_rollup(
            today - timedelta(days=30), today + timedelta(days=30), use_delivery_as_demand=False
        )
        self.assertEqual(
            future_rollup[dc.Item.gown], AssetRollup(asset=dc.Item.gown, demand=21203275, sell=1005)
        )

        # Turn of use off hospitalization projection
        future_rollup = aggregations.asset_rollup(
            today - timedelta(days=30), today + timedelta(days=30),
            use_hospitalization_projection=False,
            use_delivery_as_demand=False
        )
        self.assertEqual(
            future_rollup[dc.Item.gown], AssetRollup(asset=dc.Item.gown, demand=8757, sell=1005)
        )

    def test_mayoral_rollup(self):
        today = datetime(2020, 4, 12)
        rollup = aggregations.asset_rollup(
            today - timedelta(days=28), today,
            rollup_fn=lambda row: row.to_mayoral_category(),
            use_delivery_as_demand=False
        )
        # no uncategorized items in the rollup
        self.assertEqual(len(rollup), len(dc.MayoralCategory) - 1)
        self.assertEqual(rollup[dc.MayoralCategory.iso_gowns],
                         AssetRollup(asset=dc.MayoralCategory.iso_gowns, demand=7915269, sell=5))

        # Turn of use of hospitalization projection
        rollup = aggregations.asset_rollup(
            today - timedelta(days=28), today,
            rollup_fn=lambda row: row.to_mayoral_category(),
            use_hospitalization_projection=False,
            use_delivery_as_demand=False
        )
        self.assertEqual(rollup[dc.MayoralCategory.iso_gowns],
                         AssetRollup(asset=dc.MayoralCategory.iso_gowns, demand=4163, sell=5))

    def test_only_aggregate_active_items(self):
        today = datetime(2020, 4, 12)
        self.data_import.status = ImportStatus.replaced
        self.data_import.save()
        try:
            rollup = aggregations.asset_rollup(
                today - timedelta(days=28), today
            )
            self.assertEqual(rollup[dc.Item.gown], AssetRollup(asset=dc.Item.gown, demand=7915269, sell=0))
        finally:
            self.data_import.status = ImportStatus.active
            self.data_import.save()


class TestUnscheduledDeliveries(unittest.TestCase):
    def test_unscheduled_deliveries(self):
        data_import = DataImport(
            status=ImportStatus.active,
            data_file=DataFile.PPE_ORDERINGCHARTS_DATE_XLSX,
            file_checksum='123'
        )
        data_import.save()
        items = SourcingRow(
            item=dc.Item.gown,
            quantity=2000,
            vendor="Gown Sellers Ltd",
            description="Some gowns",
            delivery_day_1=datetime.strptime('2020-04-12', '%Y-%m-%d') - timedelta(days=5),
            delivery_day_1_quantity=5,
            delivery_day_2=datetime.strptime('2020-04-12', '%Y-%m-%d') + timedelta(days=1),
            delivery_day_2_quantity=1000,
            status='Completed',
            received_quantity=0,
            raw_data={},
        ).to_objects(ErrorCollector())

        for item in items:
            item.source = data_import
            item.save()

        purchase = Purchase.objects.filter(item=dc.Item.gown)
        self.assertEqual(purchase.count(), 1)
        self.assertEqual(purchase.first().unscheduled_quantity, 995)


class TestCategoryMappings(unittest.TestCase):
    def test_category_to_mayoral(self):
        for _, item in dc.Item.__members__.items():
            self.assertNotEqual(dc.ITEM_TO_MAYORAL.get(item), None, f"No mayoral category defined for {item}")

    def test_display_names(self):
        for _, item in dc.Item.__members__.items():
            self.assertNotEqual(dc.ITEM_TO_DISPLAYNAME.get(item), None, f"No display name defined for {item}")


class TestInventory(unittest.TestCase):
    pass


@override_settings(LOCKDOWN_ENABLED=False)
class TestViews(TestCase):
    """Sanity that the views work at a basic level"""

    def test_home(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Current status', response.content)

    def test_home_mayoral(self):
        response = self.client.get(reverse('index'), {'rollup': 'mayoral'})
        self.assertIn(b'Current status', response.content)
        self.assertEqual(response.status_code, 200)

    def test_drilldown(self):
        response = self.client.get(reverse('drilldown'), {'category': 'Eye Protection', 'rollup': 'mayoral'})
        self.assertIn(b'Incoming Supply', response.content)
        self.assertEqual(response.status_code, 200)
