import collections
import json
from pathlib import Path

from ppe import data_mappings
from ppe.data_mappings import DataType
from ppe.models import Purchase, Delivery
from xlsx_utils import import_xlsx


def run():
    path = Path('../private-data/ppe_orders.xlsx')
    data = import_xlsx(path, 'Data - Daily DCAS Sourcing', data_mappings.DCAS_DAILY_SOURCING)
    data = list(data)
    # These spreadsheets are cumulative, so drop previous data.
    n_replaced = Purchase.objects.filter(data_source=DataType.EDC_PPE, replaced=False).update(replaced=True)
    n_replaced += Delivery.objects.filter(data_source=DataType.EDC_PPE, replaced=False).update(replaced=True)
    print(f'Marked {n_replaced} objects as replaced')
    import_stats = collections.defaultdict(lambda: 0)
    for item in data:
        for obj in item.to_objects():
            import_stats[obj.__class__.__name__] += 1
            obj.save()
    print('Imported: ')
    print(json.dumps(import_stats, indent=1))
