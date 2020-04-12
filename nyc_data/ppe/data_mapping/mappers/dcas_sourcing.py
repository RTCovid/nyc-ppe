from datetime import datetime
from typing import NamedTuple, Dict

from ppe import models
from ppe.data_mapping.types import ImportedRow, repr_no_raw, DataFile
from ppe.data_mapping.utils import asset_name_to_item, parse_int, parse_date, ErrorCollector
from ppe.dataclasses import Item, OrderType
from xlsx_utils import SheetMapping, Mapping


class SourcingRow(ImportedRow, NamedTuple):
    item: Item
    description: str
    quantity: int

    vendor: str
    delivery_day_1: datetime
    delivery_day_1_quantity: int

    delivery_day_2: datetime
    delivery_day_2_quantity: int

    raw_data: Dict[str, any]

    def __repr__(self):
        # return super().repr_no_raw()
        return repr_no_raw(self)

    def sanity(self):
        delivered_quantity = (self.delivery_day_1_quantity or 0) + (
                self.delivery_day_2_quantity or 0
        )
        errors = []
        # lots of data doesn't have delivery dates.
        # if delivered_quantity > self.quantity:
        #    errors.append('Delivery > total')
        # if delivered_quantity < self.quantity:
        #    errors.append(f'Delivery < total {delivered_quantity} < {self.quantity}')
        if self.quantity is None:
            errors.append("Quantity is None")
        return errors

    def to_objects(self, error_collector: ErrorCollector):
        errors = self.sanity()
        if errors:
            error_collector.report_error(f"Refusing to generate a data model for: {self}. Errors: {errors}")
            return []
        purchase = models.Purchase(
            item=self.item,
            quantity=self.quantity,
            vendor=self.vendor,
            raw_data=self.raw_data,
            order_type=OrderType.Purchase,
            description=self.description
        )
        deliveries = []
        for day in [1, 2]:
            total = 0
            if getattr(self, f"delivery_day_{day}"):
                quantity = getattr(self, f"delivery_day_{day}_quantity")
                if quantity is None:
                    quantity = self.quantity - total
                    error_collector.report_warning(
                        f"Assuming that a null quantity means a full delivery for {self}"
                    )
                deliveries.append(
                    models.ScheduledDelivery(
                        purchase=purchase,
                        delivery_date=getattr(self, f"delivery_day_{day}"),
                        quantity=quantity,
                    )
                )
        return [purchase, *deliveries]


DCAS_DAILY_SOURCING = SheetMapping(
    sheet_name="Data - Daily DCAS Sourcing",
    data_file=DataFile.PPE_ORDERINGCHARTS_DATE_XLSX,
    mappings={
        Mapping(
            sheet_column_name="Type  Hierarchy - Critical Asset",
            obj_column_name="item",
            proc=asset_name_to_item,
        ),
        Mapping(
            sheet_column_name='Type  Hierarchy - Description',
            obj_column_name='description',
        ),
        Mapping(
            sheet_column_name="Sum of Total Ordered Individual Unit Qty",
            obj_column_name="quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Expected Delivery Date Day 1",
            obj_column_name="delivery_day_1",
            proc=parse_date,
        ),
        Mapping(
            sheet_column_name="Sum of Vendor Delivery Day 1 Estimate LD Qty",
            obj_column_name="delivery_day_1_quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Expected Delivery Date Day 2",
            obj_column_name="delivery_day_2",
            proc=parse_date,
        ),
        Mapping(
            sheet_column_name="Vendor Delivery Day 2 Estimate LD Qty",
            obj_column_name="delivery_day_2_quantity",
            proc=parse_int,
        ),
        Mapping(sheet_column_name="Type  Hierarchy - Vendor", obj_column_name="vendor"),
    },
    include_raw=True,
    obj_constructor=SourcingRow,
)