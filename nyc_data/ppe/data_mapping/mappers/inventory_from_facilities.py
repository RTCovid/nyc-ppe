from ppe.data_mapping import utils
from ppe.data_mapping.types import ImportedRow, DataFile
from ppe.data_mapping.utils import (
    ErrorCollector,
    parse_date,
    parse_int_or_zero,
)
from ppe.models import Inventory
from xlsx_utils import SheetMapping, Mapping


class InventoryRow(ImportedRow):
    def __init__(self, date, raw_data, **kwargs):
        self.date = date
        self.items = kwargs
        self.raw_data = raw_data

    def to_objects(self, error_collector: ErrorCollector):
        # The sheet has a "total" last row which is empty
        if self.date is None:
            return []
        objs = []
        for item_name, qt in self.items.items():
            item = utils.asset_name_to_item(item_name, error_collector)
            objs.append(
                Inventory(item=item, quantity=qt, as_of=self.date, raw_data=self.raw_data)
            )
        return objs


sheet_columns = [
    "N95 Respirators", "Other Respirators", "Face Masks", "Face Shields", "Goggles", "Gloves", "Gowns", "Lab Coats",
    "Ponchos", "Coveralls", "Shoe/Boot covers", "Aprons", "Vents", "Vent Parts", "Vent Medicines", "BiPaps",
    "BiPap Parts", "Multipurpose PPE", "Post Mortem Bags", "Scrubs", "Misc", "Misc Non-Deployable", "Hand Sanitizer"
]
item_mappings = [
    Mapping(
        sheet_column_name=column,
        obj_column_name=column,
        proc=parse_int_or_zero,
    )
    for column in sheet_columns
]
INVENTORY = SheetMapping(
    sheet_name="Inventory Levels",
    data_file=DataFile.FACILITY_DELIVERIES,
    mappings={
        *item_mappings,
        Mapping(sheet_column_name="Date", obj_column_name="date", proc=parse_date),
    },
    include_raw=True,
    obj_constructor=InventoryRow,
)
