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
    quantity: int
    raw_data: Dict[str, any]

    donor: str
    contact_person: str
    description: str
    picked_up: bool
    received_date: Optional[date]
    notification_date: date

    comments: str

    def __repr__(self):
        return repr_no_raw(self)

    def guess_delivery_date(self, error_collector: ErrorCollector):
        date_like = re.search("""\d+[/\-]\d+""", self.comments)
        if date_like is not None:
            return utils.parse_date(date_like.group(0), error_collector)
        else:
            return self.notification_date + timedelta(days=NUM_FUTURE_DAYS_GUESS)

    def to_objects(self, error_collector: ErrorCollector):
        if self.picked_up:
            return []
        if self.quantity is None:
            error_collector.report_warning("Ignoring donation row with no quantity")
            return []
        purchase = Purchase(
            order_type=OrderType.Donation,
            item=self.item,
            description=self.description,
            quantity=self.quantity,
            received_quantity=self.quantity if self.picked_up else 0,
            vendor=self.donor,
            comment=self.comments,
            raw_data=self.raw_data,
            donation_date=self.notification_date,
        )

        objs = [purchase]
        delivery_date = self.guess_delivery_date(error_collector)
        if delivery_date is not None:
            objs.append(
                ScheduledDelivery(
                    purchase=purchase,
                    delivery_date=delivery_date,
                    quantity=self.quantity,
                )
            )
        return objs


def date_or_pending(s: str, error_collector: ErrorCollector):
    if isinstance(s, str) and "pending" in s.lower():
        return None
    else:
        utils.parse_date(s, error_collector)


DONATION_DATA = SheetMapping(
    data_file=DataFile.CSH_DONATIONS,
    sheet_name="List of Donations",
    header_row_idx=2,
    mappings={
        Mapping(sheet_column_name="Donor", obj_column_name="donor",),
        Mapping(
            # NOTE: typo. They might fix.
            sheet_column_name="Donation notifcation Date",
            obj_column_name="notification_date",
            proc=utils.parse_date,
        ),
        Mapping(
            sheet_column_name="Person of Contact", obj_column_name="contact_person",
        ),
        Mapping(
            sheet_column_name="Detailed item description",
            obj_column_name="description",
        ),
        Mapping(
            sheet_column_name="Critical Asset",
            obj_column_name="item",
            proc=utils.asset_name_to_item,
        ),
        Mapping(
            sheet_column_name="Total Quantity ",
            obj_column_name="quantity",
            proc=utils.parse_int,
        ),
        Mapping(
            sheet_column_name="Status Shipped DOHMH  Y/N   ",
            obj_column_name="picked_up",
            proc=utils.parse_bool,
        ),
        Mapping(
            sheet_column_name="Received at CSH",
            obj_column_name="received_date",
            proc=date_or_pending,
        ),
        Mapping(
            sheet_column_name="Comments",
            obj_column_name="comments",
            proc=utils.parse_string_or_none,
        ),
    },
    include_raw=True,
    obj_constructor=DonationRow,
)
