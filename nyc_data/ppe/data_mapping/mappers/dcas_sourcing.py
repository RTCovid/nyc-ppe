from datetime import datetime
from typing import NamedTuple, Dict

from ppe import models
from ppe.data_mapping.types import ImportedRow, repr_no_raw, DataFile
from ppe.data_mapping.utils import (
    asset_name_to_item,
    parse_int,
    parse_date,
    ErrorCollector,
)
from ppe.dataclasses import Item, OrderType
from xlsx_utils import SheetMapping, Mapping, RegexMatch


class SourcingRow(ImportedRow, NamedTuple):
    status: str

    item: Item
    description: str
    quantity: int

    vendor: str
    delivery_day_1: datetime
    delivery_day_1_quantity: int

    delivery_day_2: datetime
    delivery_day_2_quantity: int

    received_quantity: int

    raw_data: Dict[str, any]

    def __repr__(self):
        return repr_no_raw(self)

    def sanity(self, error_collector: ErrorCollector):
        delivered_quantity = (self.delivery_day_1_quantity or 0) + (
            self.delivery_day_2_quantity or 0
        )
        errors = []
        # lots of data doesn't have delivery dates.
        if delivered_quantity > self.quantity:
            error_collector.report_warning(
                f"Claimed delivered quantity ({delivered_quantity}) > "
                f"total quantity {self.quantity} for {self.item} from {self.vendor}"
            )
        # if delivered_quantity < self.quantity:
        #    errors.append(f'Delivery < total {delivered_quantity} < {self.quantity}')
        if self.quantity is None:
            errors.append("Quantity is None")
        return errors

    def to_objects(self, error_collector: ErrorCollector):
        if self.status != "Completed":
            return []

        errors = self.sanity(error_collector)
        if errors:
            error_collector.report_error(
                f"Refusing to generate a data model for: {self}. Errors: {errors}"
            )
            return []
        purchase = models.Purchase(
            item=self.item,
            quantity=self.quantity,
            received_quantity=self.received_quantity,
            vendor=self.vendor,
            raw_data=self.raw_data,
            order_type=OrderType.Purchase,
            description=self.description,
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
    sheet_name=RegexMatch("DCAS \d-\d+ \d+[AP]M"),  #'DCAS 4-12 3PM',
    data_file=DataFile.PPE_ORDERINGCHARTS_DATE_XLSX,
    mappings={
        Mapping(
            sheet_column_name="Critical Asset",
            obj_column_name="item",
            proc=asset_name_to_item,
        ),
        Mapping(sheet_column_name="Description", obj_column_name="description",),
        Mapping(
            sheet_column_name="Total Qty Ordered",
            obj_column_name="quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Received Qty",
            obj_column_name="received_quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Delivery 1 Week Of",
            obj_column_name="delivery_day_1",
            proc=parse_date,
        ),
        Mapping(
            sheet_column_name="Delivery 1 Qty",
            obj_column_name="delivery_day_1_quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Deliver 2 Week Of",
            obj_column_name="delivery_day_2",
            proc=parse_date,
        ),
        Mapping(
            sheet_column_name="Delivery 2 Qty",
            obj_column_name="delivery_day_2_quantity",
            proc=parse_int,
        ),
        Mapping(sheet_column_name="Vendor", obj_column_name="vendor"),
        Mapping(sheet_column_name="Status", obj_column_name="status"),
    },
    include_raw=True,
    obj_constructor=SourcingRow,
)
