from datetime import datetime

from ppe.dataclasses import Item
from xlsx_utils import SheetMapping, Mapping


def asset_name_to_item(asset_name: str) -> Item:
    mapping = {'KN95 Masks': Item.kn95_mask,
               'Face Masks-Other': Item.mask_other,
               'Surgical Grade N95s Masks': Item.n95_mask_surgical,
               'Non-Surgical Grade N95s Masks': Item.n95_mask_non_surgical,
               'Isolation Gowns': Item.gown,
               'Coveralls': Item.coveralls,
               'Non Full Service Ventilators': Item.ventilators_non_full_service,
               'Face Coverings-Non Medical': Item.mask_other,
               'Goggles': Item.goggles,
               'Other PPE, Healthcare': Item.ppe_other,
               'Full Service Ventilators': Item.ventilators_full_service,
               'Face Shields': Item.faceshield,
               'Gloves': Item.gloves,
               'Surgical Masks': Item.mask_other
               }
    match = mapping.get(asset_name)
    if match is not None:
        return match
    print(f'Unknown type: {asset_name}')
    return Item.unknown


def parse_date(date: str):
    if isinstance(date, str):
        return datetime.strptime(date, '%m/%d/%Y')
    elif isinstance(date, datetime):
        return date
    else:
        return None


DCAS_DAILY_SOURCING = SheetMapping(
    mappings=[
        Mapping(sheet_column_name='Type  Hierarchy - Critical Asset', obj_column_name='item', proc=asset_name_to_item),
        Mapping(sheet_column_name='Sum of Total Ordered Individual Unit Qty', obj_column_name='quantity', proc=int),
        Mapping(sheet_column_name='Expected Delivery Date Day 1', obj_column_name='delivery_day_1', proc=parse_date)
    ]
)
