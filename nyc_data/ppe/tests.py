import unittest
from datetime import datetime, timedelta

from django.contrib import auth
from django.test import TestCase
from django.urls import reverse
from freezegun import freeze_time

import ppe.dataclasses as dc
from ppe import aggregations
from ppe.aggregations import AssetRollup, DemandSrc, AggColumn
from ppe.data_mapping.mappers.dcas_sourcing import SourcingRow
from ppe.data_mapping.mappers.hospital_demands import DemandRow
from ppe.data_mapping.types import DataFile
from ppe.data_mapping.utils import ErrorCollector
from ppe.dataclasses import Period
from ppe.models import (
    DataImport,
    ImportStatus,
    Purchase,
    Inventory,
    FacilityDelivery,
    Facility,
)


class TestAssetRollup(TestCase):
    def setUp(self) -> None:
        self.data_import = DataImport(
            status=ImportStatus.active,
            data_file=DataFile.PPE_ORDERINGCHARTS_DATE_XLSX,
            file_checksum="123",
        )
        self.data_import.save()
        items = SourcingRow(
            item=dc.Item.gown,
            quantity=1005,
            vendor="Gown Sellers Ltd",
            description="Some gowns",
            delivery_day_1=datetime.strptime("2020-04-12", "%Y-%m-%d")
            - timedelta(days=5),
            delivery_day_1_quantity=5,
            status="Completed",
            received_quantity=0,
            delivery_day_2=datetime.strptime("2020-04-12", "%Y-%m-%d")
            + timedelta(days=1),
            delivery_day_2_quantity=1000,
            raw_data={},
        ).to_objects(ErrorCollector())

        inventory = [
            Inventory(
                item=dc.Item.gown,
                quantity=100,
                as_of=datetime(year=2020, day=11, month=4),
                raw_data={},
            ),
            # this one is old and should be superceded
            Inventory(
                item=dc.Item.gown,
                quantity=200,
                as_of=datetime(year=2020, day=10, month=4),
                raw_data={},
            ),
        ]

        f = Facility(name="Generic Hospital", tpe=dc.FacilityType.hospital)
        items.append(f)
        deliveries = [
            FacilityDelivery(
                date=datetime(year=2020, day=10, month=4),
                quantity=1234,
                facility=f,
                item=dc.Item.gown,
            ),
            FacilityDelivery(
                date=datetime(year=2020, day=10, month=4),
                quantity=123,
                facility=f,
                item=dc.Item.faceshield,
            ),
        ]
        items += deliveries

        items += inventory

        for item in items:
            item.source = self.data_import
            item.save()

        items = DemandRow(
            item=dc.Item.gown,
            demand=2457000,
            week_start_date=datetime.strptime("2020-04-11", "%Y-%m-%d"),
            week_end_date=datetime.strptime("2020-04-17", "%Y-%m-%d"),
            raw_data={},
        ).to_objects(ErrorCollector())
        for item in items:
            item.source = self.data_import
            item.save()

    @freeze_time("2020-04-12")
    def test_rollup(self):
        today = datetime(2020, 4, 12)
        rollup = aggregations.asset_rollup_legacy(today - timedelta(days=27), today)
        self.assertEqual(len(rollup), len(dc.Item))
        # demand of 20 = 5 in the last week * 4 weeks in the period
        self.assertEqual(
            rollup[dc.Item.gown],
            AssetRollup(
                asset=dc.Item.gown,
                total_cols=AggColumn.all(),
                inventory=100,
                demand_src={DemandSrc.real_demand},
                demand=7654622,
                ordered=5,
            ),
        )

        # Turn off use of hospitalization projection
        rollup = aggregations.asset_rollup_legacy(
            today - timedelta(days=27), today, use_hospitalization_projection=False,
        )
        self.assertEqual(
            rollup[dc.Item.gown],
            AssetRollup(
                asset=dc.Item.gown,
                total_cols=AggColumn.all(),
                inventory=100,
                demand_src={DemandSrc.real_demand},
                demand=2457000 * 4,
                ordered=5,
            ),
        )

        # should fallback to past deliveries
        self.assertEqual(
            rollup[dc.Item.faceshield],
            AssetRollup(
                asset=dc.Item.faceshield,
                total_cols=AggColumn.all(),
                inventory=0,
                demand_src={DemandSrc.past_deliveries},
                demand=123 * 4,
                ordered=0,
            ),
        )

        # Turn of use off hospitalization projection & real demand
        future_rollup = aggregations.asset_rollup_legacy(
            today,
            today + timedelta(days=27),
            use_hospitalization_projection=False,
            use_real_demand=False,
        )

        # Fallback to delivery
        self.assertEqual(
            future_rollup[dc.Item.gown],
            AssetRollup(
                asset=dc.Item.gown,
                total_cols=AggColumn.all(),
                demand=1234 * 4,
                ordered=1000,
                demand_src={DemandSrc.past_deliveries},
                inventory=100,
            ),
        )

    def test_mayoral_rollup(self):
        today = datetime(2020, 4, 12)
        rollup = aggregations.asset_rollup_legacy(
            today - timedelta(days=27),
            today,
            rollup_fn=lambda row: row.to_mayoral_category(),
        )
        # no uncategorized items in the rollup
        self.assertEqual(len(rollup), len(dc.MayoralCategory) - 1)
        self.assertEqual(
            rollup[dc.MayoralCategory.iso_gowns].asset, dc.MayoralCategory.iso_gowns
        )

    def test_only_aggregate_active_items(self):
        today = datetime(2020, 4, 12)
        self.data_import.status = ImportStatus.replaced
        self.data_import.save()
        try:
            self.assertEqual(aggregations.known_recent_demand(), {})
            rollup = aggregations.asset_rollup_legacy(today - timedelta(days=28), today)
            self.assertEqual(
                rollup[dc.Item.gown],
                AssetRollup(
                    asset=dc.Item.gown, total_cols=AggColumn.all(), demand=0, ordered=0
                ),
            )
        finally:
            self.data_import.status = ImportStatus.active
            self.data_import.save()


class TestUnscheduledDeliveries(unittest.TestCase):
    def test_unscheduled_deliveries(self):
        data_import = DataImport(
            status=ImportStatus.active,
            data_file=DataFile.PPE_ORDERINGCHARTS_DATE_XLSX,
            file_checksum="123",
        )
        data_import.save()
        items = SourcingRow(
            item=dc.Item.gown,
            quantity=2000,
            vendor="Gown Sellers Ltd",
            description="Some gowns",
            delivery_day_1=datetime.strptime("2020-04-12", "%Y-%m-%d")
            - timedelta(days=5),
            delivery_day_1_quantity=5,
            delivery_day_2=datetime.strptime("2020-04-12", "%Y-%m-%d")
            + timedelta(days=1),
            delivery_day_2_quantity=1000,
            status="Completed",
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
            self.assertNotEqual(
                dc.ITEM_TO_MAYORAL.get(item),
                None,
                f"No mayoral category defined for {item}",
            )

    def test_display_names(self):
        for _, item in dc.Item.__members__.items():
            self.assertNotEqual(
                dc.ITEM_TO_DISPLAYNAME.get(item),
                None,
                f"No display name defined for {item}",
            )


class TestViews(TestCase):
    """Sanity that the views work at a basic level"""

    def setUp(self):
        self.client.force_login(
            auth.get_user_model().objects.create_superuser(username="testuser")
        )

    def test_home(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Current status", response.content)

    def test_home_mayoral(self):
        response = self.client.get(reverse("index"), {"rollup": "mayoral"})
        self.assertIn(b"Current status", response.content)
        self.assertEqual(response.status_code, 200)

    def test_drilldown(self):
        response = self.client.get(
            reverse("drilldown"), {"category": "Eye Protection", "rollup": "mayoral"}
        )
        self.assertIn(b"Incoming Supply", response.content)
        self.assertEqual(response.status_code, 200)


class TestPeriod(unittest.TestCase):
    def test_period_len(self):
        start = datetime.strptime("2020-04-11", "%Y-%m-%d")
        end = datetime.strptime("2020-04-17", "%Y-%m-%d")
        self.assertEqual(Period(start, end).inclusive_length(), timedelta(days=7))

        self.assertEqual(
            Period(start, start + timedelta(days=6)).inclusive_length(),
            timedelta(days=7),
        )


class TestRollupObj(unittest.TestCase):
    def test_rollup_obj(self):
        rollup = AssetRollup(
            asset=dc.Item.gown,
            total_cols={AggColumn.Ordered, AggColumn.Made},
            donated=100,
            made=456,
            ordered=789,
            demand=0,
            demand_src=set(),
        )

        self.assertEqual(rollup.total, 789 + 456)
