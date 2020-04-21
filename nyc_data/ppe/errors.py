from typing import List

from fuzzywuzzy import process


class DataImportError(Exception):
    pass


class NoMappingForFileError(DataImportError):
    pass


class PartialFile(DataImportError):
    def __init__(self, expected_sheets, actual_sheets):
        self.expected_sheets = expected_sheets
        self.actual_sheets = actual_sheets

    def __str__(self):
        delta = delta_hint(self.expected_sheets, self.actual_sheets)
        hint = "\n".join(
            [f"Did you rename '{k}' to '{v}'?" for k, (v, _) in delta.items()]
        )
        return f"We expected to find {self.expected_sheets} in this file, but we found {self.actual_sheets}. Hint: {hint}"


def delta_hint(expected: List[str], found: List[str]):
    missing_columns = set(expected).difference(found)
    ret = {}
    for column in missing_columns:
        (possible_rename, score) = process.extractOne(column, found)
        if score > 80:
            ret[column] = (possible_rename, score)
    return ret


class ImportInProgressError(DataImportError):
    def __init__(self, import_id):
        self.import_id = import_id


class SheetNameMismatch(DataImportError):
    def __init__(self, sheet_names, best_guess):
        self.sheet_names = sheet_names
        self.buest_guess = best_guess

    def __str__(self):
        return f"This spreadsheet didn't have a sheet name we understand.\n Our best guess is that '{self.buest_guess[0]}' should be '{self.buest_guess[1]}'"


class ColumnNameMismatch(DataImportError):
    def __init__(self, our_cols, their_cols):
        self.our_cols = our_cols
        self.their_cols = their_cols

    def delta(self):
        missing_columns = set(self.our_cols).difference(self.their_cols)
        ret = {}
        for column in missing_columns:
            (possible_rename, score) = process.extractOne(column, self.their_cols)
            ret[column] = possible_rename
        return ret

    def __str__(self):
        delta = self.delta()
        matches = "\n".join(
            [
                f'We were looking for "{us}" (we found "{them}" which looked similar)'
                for (us, them) in delta.items()
            ]
        )
        return f"{len(delta)} missing columns. {matches}"


class CsvImportError(DataImportError):
    pass
