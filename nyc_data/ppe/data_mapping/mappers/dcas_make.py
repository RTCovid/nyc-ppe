from datetime import datetime, timedelta
from enum import Enum
from typing import NamedTuple, Dict, Optional

from ppe import models
from ppe.data_mapping.types import ImportedRow, repr_no_raw, DataFile
from ppe.data_mapping.utils import (
    parse_date,
    asset_name_to_item,
    parse_int,
    ErrorCollector,
)
from ppe.dataclasses import Item, OrderType
from xlsx_utils import SheetMapping, Mapping


class ContractStatus(str, Enum):
    executed = "executed"
    in_progress = "inprogress"
    preliminary = "preliminary"


def parse_contract_status(status, error_collector: ErrorCollector):
    status = (status or "").replace(" ", "").lower()
    try:
        return ContractStatus(status)
    except ValueError:
        error_collector.report_error(f'Unknown contract status: "{status}"')
        return None


class MakeRow(ImportedRow, NamedTuple):
    item: Item
    quantity: int
    raw_data: Dict[str, any]
    delivery_date: Optional[datetime]
    # used to handle stuff like `TBD` and `weekly until 5/30`
    raw_date: Optional[str]

    vendor: Optional[str]

    contract_status: ContractStatus

    def __repr__(self):
        return repr_no_raw(self)

    def sanity(self):
        if self.quantity is None:
            return ["Quantity is none"]
        if self.vendor is None:
            return ["Vendor is none"]

    def to_objects(self, error_collector: ErrorCollector):
        if self.contract_status != ContractStatus.executed:
            return []
        errors = self.sanity()
        if errors:
            error_collector.report_error(
                f"Refusing to generate a data model for: {self}. Errors: {errors}"
            )
            return []
        purchase = models.Purchase(
            item=self.item,
            quantity=self.quantity,
            vendor=self.vendor,
            raw_data=self.raw_data,
            order_type=OrderType.Make,
        )
        dates = []
        if self.delivery_date:
            dates.append(self.delivery_date)
        elif "weekly" in self.raw_date:
            import re

            date_str = re.sub(r"[a-zA-Z ]+", "", self.raw_date).strip()
            end_date = parse_date(date_str, error_collector)
            if end_date:
                dates = []
                while end_date > datetime.today():
                    dates.append(end_date)
                    end_date -= timedelta(weeks=1)

        delivery = [
            models.ScheduledDelivery(
                purchase=purchase, delivery_date=date, quantity=self.quantity,
            )
            for date in dates
        ]

        return [purchase, *delivery]


SUPPLIERS_AND_PARTNERS = SheetMapping(
    data_file=DataFile.SUPPLIERS_PARTNERS_XLSX,
    sheet_name="Wkly Delivery Tracker - CH",
    mappings={
        Mapping(
            sheet_column_name="Supply / Service",
            obj_column_name="item",
            proc=asset_name_to_item,
        ),
        Mapping(
            sheet_column_name="Number of Units",
            obj_column_name="quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Delivery Date",
            obj_column_name="delivery_date",
            proc=parse_date,
        ),
        Mapping(sheet_column_name="Delivery Date", obj_column_name="raw_date"),
        Mapping(
            sheet_column_name="Counterparty Name (for procurement)",
            obj_column_name="vendor",
        ),
        Mapping(
            sheet_column_name="Contract Status",
            obj_column_name="contract_status",
            proc=parse_contract_status,
        ),
    },
    include_raw=True,
    obj_constructor=MakeRow,
)
