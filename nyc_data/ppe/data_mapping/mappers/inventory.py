from typing import NamedTuple, Dict

from ppe import models
from ppe.data_mapping.types import ImportedRow, repr_no_raw, DataFile
from ppe.data_mapping.utils import asset_name_to_item, parse_int
from ppe.dataclasses import Item
from xlsx_utils import SheetMapping, Mapping


class InventoryRow(ImportedRow, NamedTuple):
    raw_data: Dict[str, any]
    item: Item
    quantity: int

    def to_objects(self, error_collector):
        return [
            models.Inventory(
                item=self.item,
                raw_data=self.raw_data,
                quantity=self.quantity,
            )
        ]

    def __repr__(self):
        return repr_no_raw(self)


INVENTORY = SheetMapping(
    sheet_name='InventoryHand',
    data_file=DataFile.INVENTORY,
    mappings={
        Mapping(
            sheet_column_name="Item",
            obj_column_name="item",
            proc=asset_name_to_item,
        ),
        Mapping(
            sheet_column_name="CITY",
            obj_column_name="quantity",
            proc=parse_int
        )
    },
    include_raw=True,
    obj_constructor=InventoryRow
)