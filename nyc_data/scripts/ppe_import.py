from pathlib import Path

from ppe.data_import import full_import
from ppe.data_mappings import DataSource


def run():
    print("Importing PPEs purchased")
    path = Path("../private-data/ppe_orders.xlsx")
    if path.exists():
        full_import(path, DataSource.EDC_PPE, overwrite_in_prog=True)
    else:
        print(f'No file to import @ {path}')

    print("Importing PPE made")
    path = Path("../private-data/ppe_make.xlsx")
    if path.exists():
        full_import(path, DataSource.EDC_MAKE)
    else:
        print(f'No file to import @ {path}')

    print('Importing inventory')
    path = Path('../private-data/inventory.xlsx')
    if path.exists():
        full_import(path, DataSource.INVENTORY)
    else:
        print(f'No file to import @ {path}')
