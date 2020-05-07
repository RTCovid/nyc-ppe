import re
from datetime import date, timedelta
from typing import NamedTuple, Dict, Optional

from ppe.data_mapping import utils
from ppe.data_mapping.types import ImportedRow, DataFile, repr_no_raw
from ppe.data_mapping.utils import ErrorCollector
from ppe.dataclasses import Item, OrderType
from ppe.models import Purchase, ScheduledDelivery
from xlsx_utils import SheetMapping, Mapping

NUM_FUTURE_DAYS_GUESS = 5


class DonationRow(ImportedRow, NamedTuple):
    item: Item
    raw_data: Dict[str, any]

    donor: str
    contact_person: str
    description: str
    notification_date: date
    # quantity delivered to end recipient (already in inventory, concievably)
    total_distributed_quantity: int

    # quantity pledged by donor
    total_pledged_quantity: int

    distributed_to: str
    distribution_status: str

    def __repr__(self):
        return repr_no_raw(self)

    def to_objects(self, error_collector: ErrorCollector):
        purchase = Purchase(
            order_type=OrderType.Donation,
            item=self.item,
            description=self.description,
            quantity=self.total_pledged_quantity,
            received_quantity=self.total_distributed_quantity,
            vendor=self.donor,
            raw_data=self.raw_data,
            donation_date=self.notification_date,
        )

        return [purchase]


def date_or_pending(s: str, error_collector: ErrorCollector):
    if isinstance(s, str) and "pending" in s.lower():
        return None
    else:
        utils.parse_date(s, error_collector)


DONATION_DATA = SheetMapping(
    data_file=DataFile.CSH_DONATIONS,
    sheet_name="{e9b4915b-d988-ea11-a328-64006a",
    header_row_idx=2,
    mappings={
        Mapping(sheet_column_name="Donor", obj_column_name="donor",),
        Mapping(
            sheet_column_name="Notified Date",
            obj_column_name="notification_date",
            proc=utils.parse_date,
        ),
        Mapping(
            sheet_column_name="Person Of Contact", obj_column_name="contact_person",
        ),
        Mapping(
            sheet_column_name="Detailed Item Description",
            obj_column_name="description",
        ),
        Mapping(
            sheet_column_name="Critical Asset",
            obj_column_name="item",
            proc=utils.asset_name_to_item,
        ),
        Mapping(
            sheet_column_name="Total Notified Quantity",
            obj_column_name="total_pledged_quantity",
            proc=utils.parse_int,
        ),
        Mapping(
            sheet_column_name="Total Distributed Quantity",
            obj_column_name="total_distributed_quantity",
            proc=utils.parse_int_or_zero,
        ),
        Mapping(
            sheet_column_name="Distribution Status",
            obj_column_name="distribution_status",

        ),
        Mapping(
            sheet_column_name="Distributed To",
            obj_column_name="distributed_to"
        )
    },
    include_raw=True,
    obj_constructor=DonationRow,
)
