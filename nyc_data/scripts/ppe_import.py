from datetime import date
from pathlib import Path

import ppe.errors
from ppe import data_import


def run(path=None):
    if path is None:
        private_data_dir = Path("../private-data")
        xlsx_files = [
            f for f in private_data_dir.iterdir() if f.suffix in {".xlsx", ".csv"}
        ]
    else:
        xlsx_files = [Path(path)]

    print(f"Found {len(xlsx_files)} xlsx files in private-data")
    for file in xlsx_files:
        try:
            print(f"---- Importing {file} ----")
            import_obj = data_import.smart_import(
                path=file,
                uploader_name="Uploaded via CLI",
                current_as_of=date.today(),
                overwrite_in_prog=True,
            )
            data_import.finalize_import(import_obj)
        except ppe.errors.NoMappingForFileError:
            print(f"{file} does not appear to be a format we recognize")
        except ppe.errors.PartialFile:
            print(
                f"{file} appears to have changed and does not match the format anymore"
            )
        finally:
            print(f"---- Import of {file} complete ----")
            print()
            print()
