import os
from pathlib import Path

import xlsx_utils
from ppe import data_import
from ppe.data_import import ALL_MAPPINGS


def run():
    private_data_dir = Path('../private-data')
    xlsx_files = [f for f in private_data_dir.iterdir() if f.suffix == '.xlsx']
    print(f"Found {len(xlsx_files)} xlsx files in private-data")
    for file in xlsx_files:
        try:
            print(f'---- Importing {file} ----')
            import_obj = data_import.smart_import(file, 'Uploaded via CLI', overwrite_in_prog=True)
            data_import.complete_import(import_obj)
        except data_import.NoMappingForFileError:
            print(f"{file} does not appear to be a format we recognize")
        finally:
            print(f'---- Import of {file} complete ----')
            print()
            print()
