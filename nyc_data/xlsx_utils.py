from pathlib import Path
from typing import NamedTuple, Any, Callable, List, Optional

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
    mappings: List[Mapping]
    obj_constructor: Optional[Callable[[Any], Any]] = None


def import_xlsx(sheet: Path, sheet_name: str, sheet_mapping: SheetMapping):
    workbook = load_workbook(sheet)
    sheet = workbook[sheet_name]
    as_dicts = XLSXDictReader(sheet)
    for row in as_dicts:
        mapped_row = {}
        for mapping in sheet_mapping.mappings:
            item = row[mapping.sheet_column_name]
            if mapping.proc:
                item = mapping.proc(item)
            mapped_row[mapping.obj_column_name] = item
        if sheet_mapping.obj_constructor:
            yield sheet_mapping.obj_constructor(mapped_row)
        else:
            yield mapped_row
