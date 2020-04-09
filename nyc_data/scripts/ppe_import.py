from pathlib import Path

from ppe import data_mappings
from xlsx_utils import import_xlsx


def run():
    path = Path('../private-data/ppe_orders.xlsx')
    data = import_xlsx(path, 'Data - Daily DCAS Sourcing', data_mappings.DCAS_DAILY_SOURCING)
    data = list(data)
    print(data)
