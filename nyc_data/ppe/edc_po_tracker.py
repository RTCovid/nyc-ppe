from datetime import datetime
from typing import NamedTuple, Dict, Optional

from ppe import models
from ppe.data_mapping.types import ImportedRow, repr_no_raw, DataFile
from ppe.data_mapping.utils import (
    parse_date,
    asset_name_to_item,
    ErrorCollector,
    parse_int_or_zero)
from ppe.dataclasses import OrderType
from xlsx_utils import SheetMapping, Mapping


class MakeRow(ImportedRow, NamedTuple):
    iso_gowns: int
    face_shields: int
    delivery_date: Optional[datetime]
    raw_data: Dict[str, any]

    def __repr__(self):
        return repr_no_raw(self)


    def to_objects(self, error_collector: ErrorCollector):

        objs = []
        for mapping in item_mappings:
            item = asset_name_to_item(mapping.sheet_column_name, error_collector)
            quantity = getattr(self, mapping.obj_column_name)
            purchase = models.Purchase(
                item=item,
                quantity=quantity,
                vendor="Aggregate Data (no vendor available)",
                raw_data=self.raw_data,
                order_type=OrderType.Make,
            )

            delivery = models.ScheduledDelivery(
                purchase=purchase, delivery_date=self.delivery_date, quantity=quantity,
            )

            objs.append(purchase)
            objs.append(delivery)

        return objs


sheet_columns = [
    "Face Shields",
    "ISO Gowns "
]

item_mappings = [
    Mapping(
        sheet_column_name=column,
        obj_column_name=column.strip().lower().replace(" ", "_"),
        proc=parse_int_or_zero,
    )
    for column in sheet_columns
]

EDC_PO_TRACKER = SheetMapping(
    data_file=DataFile.SUPPLIERS_PARTNERS_XLSX,
    sheet_name="Daily Delivery Roll up",
    mappings={
        *item_mappings,
        Mapping(sheet_column_name="Date", obj_column_name="delivery_date", proc=parse_date),
    },
    include_raw=True,
    obj_constructor=MakeRow,
    header_row_idx=3
)
