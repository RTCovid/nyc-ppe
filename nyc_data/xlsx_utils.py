import csv
import json
from pathlib import Path
from typing import NamedTuple, Any, Callable, List, Optional, Set

from django.core.serializers.json import DjangoJSONEncoder
from openpyxl import load_workbook

from ppe import errors
from ppe.data_mapping.types import DataFile
from ppe.data_mapping.utils import ErrorCollector


def XLSXDictReader(sheet):
    rows = sheet.max_row
    cols = sheet.max_column

    def item(i, j):
        return sheet.cell(row=1, column=j).value, sheet.cell(row=i, column=j).value

    return (dict(item(i, j) for j in range(1, cols + 1)) for i in range(2, rows + 1))


class Mapping(NamedTuple):
    sheet_column_name: str
    obj_column_name: str
    proc: Optional[Callable[[str, ErrorCollector], Any]] = None


class SheetMapping(NamedTuple):
    data_file: DataFile
    sheet_name: Optional[str]  # None for CSV
    mappings: Set[Mapping]
    include_raw: bool
    obj_constructor: Optional[Callable[[Any], "ImportedRow"]] = None


RAW_DATA = "raw_data"


def guess_mapping(sheet: Path, possible_mappings: List[SheetMapping]):
    workbook = None
    if sheet.suffix == '.xlsx':
        workbook = load_workbook(sheet, data_only=True)
        possible_mappings = [m for m in possible_mappings if m.sheet_name in workbook.sheetnames]
    elif sheet.suffix == '.csv':
        possible_mappings = [m for m in possible_mappings if m.sheet_name is None]
    else:
        return []
    final_mappings = []

    for mapping in possible_mappings:
        if mapping.sheet_name is not None and workbook:
            sheet = workbook[mapping.sheet_name]
            first_row = next(XLSXDictReader(sheet))

        else:

            try:
                with open(sheet, encoding="latin-1") as csvfile:
                    reader = csv.DictReader(csvfile)
                    first_row = next(reader)
                    
            except Exception as exc:
                raise errors.CsvImportError('Error reading in CSV file') from exc

        col_names = [m.sheet_column_name for m in mapping.mappings]
        if all(col_name in first_row for col_name in col_names):
            final_mappings.append(mapping)
        elif mapping.sheet_name is not None:
            print(
                "We expected: ",
                set(col_names).difference(first_row.keys()),
                "we found: ",
                first_row.keys(),
            )
            raise Exception(
                f"Sheetname matches but column names do not {sheet} {mapping.data_file}"
            )

    return final_mappings


def import_xlsx(
    sheet: Path,
    sheet_mapping: SheetMapping,
    error_collector: ErrorCollector = lambda: ErrorCollector(),
):
    if sheet_mapping.sheet_name is not None:
        workbook = load_workbook(sheet, data_only=True)
        sheet = workbook[sheet_mapping.sheet_name]
        as_dicts = XLSXDictReader(sheet)
    else:
        with open(sheet, encoding="latin-1") as csvfile:
            reader = csv.DictReader(csvfile)
            as_dicts = list(reader)

    for row in as_dicts:
        mapped_row = {}
        if all(el is None for el in row.values()):
            continue
        for mapping in sheet_mapping.mappings:
            item = row[mapping.sheet_column_name]
            if mapping.proc:
                item = mapping.proc(item, error_collector)
            mapped_row[mapping.obj_column_name] = item

        if sheet_mapping.include_raw:
            # allow serialization of datetimes
            mapped_row[RAW_DATA] = json.dumps(row, cls=DjangoJSONEncoder)
        if sheet_mapping.obj_constructor:
            yield sheet_mapping.obj_constructor(**mapped_row)
        else:
            yield mapped_row
