from typing import NamedTuple, Dict, Any
from datetime import date

from ppe.data_mapping.types import DataFile, ImportedRow
from ppe.data_mapping.utils import (
    parse_int_or_zero,
    parse_date,
    asset_name_to_item,
    ErrorCollector,
)
from ppe.models import Demand
from xlsx_utils import SheetMapping, Mapping


class DemandRow(ImportedRow, NamedTuple):
    item: str
    demand: int
    week_start_date: date
    week_end_date: date

    raw_data: Dict[str, Any]

    def to_objects(self, error_collector):
        return [
            Demand(
                item=self.item,
                demand=self.demand,
                start_date=self.week_start_date,
                end_date=self.week_end_date,
            )
        ]


sheet_columns = ["Item", "Demand", "Week Start", "Week End"]


WEEKLY_DEMANDS = SheetMapping(
    sheet_name=None,
    data_file=DataFile.HOSPITAL_DEMANDS,
    mappings={
        Mapping(
            sheet_column_name="Item", obj_column_name="item", proc=asset_name_to_item,
        ),
        Mapping(
            sheet_column_name="Demand", obj_column_name="demand", proc=parse_int_or_zero
        ),
        Mapping(
            sheet_column_name="Week Start",
            obj_column_name="week_start_date",
            proc=parse_date,
        ),
        Mapping(
            sheet_column_name="Week End",
            obj_column_name="week_end_date",
            proc=parse_date,
        ),
    },
    obj_constructor=DemandRow,
    include_raw=True,
)
