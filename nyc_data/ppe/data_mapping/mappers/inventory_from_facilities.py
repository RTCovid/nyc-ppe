from datetime import date
from typing import NamedTuple, Dict, Any

from ppe.data_mapping.types import ImportedRow, DataFile
from ppe.data_mapping.utils import (
    ErrorCollector,
    parse_int,
    parse_date,
    parse_int_or_zero,
)
from ppe.dataclasses import Item
from ppe.models import Inventory
from xlsx_utils import SheetMapping, Mapping


class InventoryRow(ImportedRow, NamedTuple):
    date: date
    n95_respirators: int
    face_masks: int
    eyewear: int
    gloves: int
    gowns: int
    ponchos: int
    coveralls: int
    vents: int
    bipaps: int
    multipurpose_ppe: int
    post_mortem_bags: int
    scrubs: int

    raw_data: Dict[str, Any]

    def to_objects(self, error_collector: ErrorCollector):
        objs = [
            Inventory(item=Item.n95_mask_surgical, quantity=self.n95_respirators),
            Inventory(item=Item.mask_other, quantity=self.face_masks,),
            Inventory(item=Item.generic_eyeware, quantity=self.eyewear,),
            Inventory(item=Item.gloves, quantity=self.gloves,),
            Inventory(item=Item.gown, quantity=self.gowns,),
            Inventory(item=Item.ponchos, quantity=self.ponchos,),
            Inventory(item=Item.coveralls, quantity=self.coveralls,),
            Inventory(item=Item.ventilators_full_service, quantity=self.vents,),
            Inventory(item=Item.bipap_machines, quantity=self.bipaps,),
            Inventory(item=Item.ppe_other, quantity=self.multipurpose_ppe,),
            Inventory(item=Item.body_bags, quantity=self.post_mortem_bags,),
            Inventory(item=Item.scrubs, quantity=self.scrubs,),
        ]

        for obj in objs:
            obj.raw_data = self.raw_data
            obj.as_of = self.date
        return objs


sheet_columns = [
    "N95 Respirators",
    "Face Masks",
    "Eyewear",
    "Gloves",
    "Gowns",
    "Ponchos",
    "Coveralls",
    "Vents",
    "BiPaps",
    "Multipurpose PPE",
    "Post Mortem Bags",
    "Scrubs",
]
item_mappings = [
    Mapping(
        sheet_column_name=column,
        obj_column_name=column.lower().replace(" ", "_"),
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
