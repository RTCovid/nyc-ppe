from typing import NamedTuple

from ppe.data_mapping import utils
from ppe.data_mapping.types import DataFile, ImportedRow
from ppe.data_mapping.utils import parse_int_or_zero, parse_date, ErrorCollector
from ppe.dataclasses import Item
from ppe.models import FacilityDelivery, Facility
from xlsx_utils import SheetMapping, Mapping


class DeliveryRow(ImportedRow):
    def __init__(
            self, date, facility_type: str, facility_name: str, raw_data, **kwargs
    ):
        self.date = date
        self.facility_type = facility_type
        self.facility_name = facility_name
        self.raw_data = raw_data
        self.items = kwargs

    def to_objects(self, error_collector: ErrorCollector):
        # The sheet has a "total" last row which is empty
        if self.date is None:
            return []
        objs = []
        #facility = Facility.active().filter(name=self.facility_name).first()
        #if not facility:
        #    facility = Facility(name=self.facility_name, tpe=self.facility_type)
        #    objs.append(facility)

        for item_name, qt in self.items.items():
            item = utils.asset_name_to_item(item_name, error_collector)
            objs.append(
                FacilityDelivery(
                    date=self.date, facility=None, item=item, quantity=qt
                )
            )
        return objs


sheet_columns = [
    "N95 Respirators", "Other Respirators", "Face Masks", "Face Shields", "Goggles", "Gloves", "Gowns", "Ponchos",
    "Aprons", "Vents", "Ventilator Parts", "Post Mortem Bags", "BiPap", "BiPap Parts", "Coveralls", "Shoe/Boot Covers",
    "Scrubs", "Multipurpose PPE", "Hand Sanitizer", "Misc", "Misc Non-Deployable"
]

item_mappings = [
    Mapping(
        sheet_column_name=column,
        obj_column_name=column,
        proc=parse_int_or_zero,
    )
    for column in sheet_columns
]

FACILITY_DELIVERIES = SheetMapping(
    sheet_name="Facility Deliveries Summaries",
    data_file=DataFile.FACILITY_DELIVERIES,
    mappings={
        Mapping(sheet_column_name="Date", obj_column_name="date", proc=parse_date),
        Mapping(
            sheet_column_name="Facility Name or Network",
            obj_column_name="facility_name",
        ),
        Mapping(sheet_column_name="Facility Type", obj_column_name="facility_type"),
        *item_mappings,
    },
    obj_constructor=DeliveryRow,
    include_raw=True,
)
