import collections
import json
from pathlib import Path

from ppe import data_mappings
from ppe.data_import import import_data, complete_import, full_import
from ppe.data_mappings import DataSource
from ppe.models import Purchase, Delivery
from xlsx_utils import import_xlsx, SheetMapping


def do_import(path: Path, mapping: SheetMapping, data_type: DataSource):
    data = import_xlsx(path, mapping.sheet_name, mapping)
    data = list(data)
    # These spreadsheets are cumulative, so drop previous data.
    n_replaced = Purchase.objects.filter(data_source=data_type, replaced=False).update(
        replaced=True
    )
    n_replaced += Delivery.objects.filter(data_source=data_type, replaced=False).update(
        replaced=True
    )
    print(f"Marked {n_replaced} objects as replaced")
    import_stats = collections.defaultdict(lambda: 0)
    for item in data:
        for obj in item.to_objects():
            import_stats[obj.__class__.__name__] += 1
            obj.save()
    print("Imported: ")
    print(json.dumps(import_stats, indent=1))


def run():
    print("Importing PPEs purchased")
    path = Path("../private-data/ppe_orders.xlsx")
    full_import(path, DataSource.EDC_PPE, overwrite_in_prog=True)

    print("Importing PPE made")
    path = Path("../private-data/ppe_make.xlsx")
    full_import(path, DataSource.EDC_MAKE)

    print('Importing inventory')
    path = Path('../private-data/inventory.xlsx')
    full_import(path, DataSource.INVENTORY)
