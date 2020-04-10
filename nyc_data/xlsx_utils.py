import json
from pathlib import Path
from typing import NamedTuple, Any, Callable, List, Optional

from django.core.serializers.json import DjangoJSONEncoder
from openpyxl import load_workbook


def XLSXDictReader(sheet):
    rows = sheet.max_row
    cols = sheet.max_column

    def item(i, j):
        return sheet.cell(row=1, column=j).value, sheet.cell(row=i, column=j).value

    return (dict(item(i, j) for j in range(1, cols + 1)) for i in range(2, rows + 1))


class Mapping(NamedTuple):
    sheet_column_name: str
    obj_column_name: str
    proc: Optional[Callable[[str], Any]] = None


class SheetMapping(NamedTuple):
    sheet_name: str
    mappings: List[Mapping]
    include_raw: bool
    obj_constructor: Optional[Callable[[Any], Any]] = None


RAW_DATA = "raw_data"


def import_xlsx(sheet: Path, sheet_name: str, sheet_mapping: SheetMapping):
    workbook = load_workbook(sheet)
    sheet = workbook[sheet_name]
    as_dicts = XLSXDictReader(sheet)
    for row in as_dicts:
        mapped_row = {}
        if all(el is None for el in row.values()):
            continue
        for mapping in sheet_mapping.mappings:
            item = row[mapping.sheet_column_name]
            if mapping.proc:
                item = mapping.proc(item)
            mapped_row[mapping.obj_column_name] = item

        if sheet_mapping.include_raw:
            # allow serialization of datetimes
            mapped_row[RAW_DATA] = json.dumps(row, cls=DjangoJSONEncoder)
        if sheet_mapping.obj_constructor:
            yield sheet_mapping.obj_constructor(**mapped_row)
        else:
            yield mapped_row
