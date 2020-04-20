import csv
import json
from pathlib import Path
from typing import NamedTuple, Any, Callable, List, Optional, Set
from fuzzywuzzy import process

from django.core.serializers.json import DjangoJSONEncoder
from openpyxl import load_workbook

from ppe import errors
from ppe.data_mapping.types import DataFile
from ppe.data_mapping.utils import ErrorCollector
from ppe.errors import ColumnNameMismatch, PartialFile


def XLSXDictReader(sheet, header_row):
    rows = sheet.max_row
    cols = sheet.max_column

    def item(i, j):
        return sheet.cell(row=header_row, column=j).value, sheet.cell(row=i, column=j).value

    return (dict(item(i, j) for j in range(1, cols + 1)) for i in range(header_row + 1, rows + 1))


class Mapping(NamedTuple):
    sheet_column_name: str
    obj_column_name: str
    proc: Optional[Callable[[str, ErrorCollector], Any]] = None


class SheetMapping(NamedTuple):
    data_file: DataFile
    sheet_name: Optional[str]  # None for CSV
    mappings: Set[Mapping]
    include_raw: bool
    obj_constructor: Optional[Callable[[Any], "ImportedRow"]]
    header_row_idx: int = 1

    def key_columns(self):
        return (mapping.sheet_column_name for mapping in self.mappings)


RAW_DATA = "raw_data"


def guess_mapping(sheet: Path, all_mappings: List[SheetMapping]):
    workbook = None
    if sheet.suffix == '.xlsx':
        workbook = load_workbook(sheet, data_only=True)
        possible_mappings = [m for m in all_mappings if m.sheet_name in workbook.sheetnames]
        if not possible_mappings:
            known_sheetnames = [m.sheet_name for m in all_mappings]
            matches = [(us, process.extractOne(us, known_sheetnames)) for us in workbook.sheetnames]
            raise errors.SheetNameMismatch(workbook.sheetnames, (matches[0][0], matches[0][1][0]))
        else:
            df = possible_mappings[0].data_file

            if len([m for m in all_mappings if m.data_file == df]) != len(possible_mappings):
                expected = [m.sheet_name for m in all_mappings if m.data_file == df]
                raise errors.PartialFile(expected_sheets=expected, actual_sheets=workbook.sheetnames)

    elif sheet.suffix == '.csv':
        possible_mappings = [m for m in all_mappings if m.sheet_name is None]
    else:
        return []
    final_mappings = []

    for mapping in possible_mappings:
        if mapping.sheet_name is not None and workbook:
            sheet = workbook[mapping.sheet_name]
            first_row = next(XLSXDictReader(sheet, header_row=mapping.header_row_idx or 1))
        else:
            try:
                with open(sheet, encoding="latin-1") as csvfile:
                    text = csvfile.read()
            except Exception as exc:
                raise errors.CsvImportError('Error reading in CSV file') from exc

            reader = csv.DictReader(text.splitlines())
            first_row = next(reader)

        col_names = [m.sheet_column_name for m in mapping.mappings]
        if all(col_name in first_row for col_name in col_names):
            final_mappings.append(mapping)
        elif mapping.sheet_name is not None:
            raise ColumnNameMismatch(col_names, first_row.keys())

    if final_mappings:
        return final_mappings


def import_xlsx(
        sheet: Path,
        sheet_mapping: SheetMapping,
        error_collector: ErrorCollector = lambda: ErrorCollector(),
):
    if sheet_mapping.sheet_name is not None:
        workbook = load_workbook(sheet, data_only=True)
        sheet = workbook[sheet_mapping.sheet_name]
        as_dicts = XLSXDictReader(sheet, sheet_mapping.header_row_idx)
    else:
        with open(sheet, encoding="latin-1") as csvfile:
            reader = csv.DictReader(csvfile)
            as_dicts = list(reader)

    for row in as_dicts:
        mapped_row = {}
        if all(row.get(col) is None for col in sheet_mapping.key_columns()):
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
