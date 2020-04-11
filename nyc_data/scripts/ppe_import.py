import os
from pathlib import Path

import xlsx_utils
from ppe.data_import import MAPPINGS
from ppe import data_import


def run():
    private_data_dir = Path('../private-data')
    xlsx_files = [f for f in private_data_dir.iterdir() if f.suffix == '.xlsx']
    print(f"Found {len(xlsx_files)} xlsx files in private-data")
    for file in xlsx_files:
        possible_mappings = xlsx_utils.guess_mapping(file, MAPPINGS.values())
        if len(possible_mappings) == 0:
            print(f'No mapping found for {file}, ignoring')
        elif len(possible_mappings) > 1:
            print(f'Multiple mappings found for {file}. This is weird (ignoring)!')
        else:
            inferred_mapping = possible_mappings[0]
            print(f'Importing {file} inferred to be {inferred_mapping}')
            data_source = [src for (src, mapping) in MAPPINGS.items() if mapping == inferred_mapping][0]
            data_import.full_import(file, data_source, overwrite_in_prog=True)

