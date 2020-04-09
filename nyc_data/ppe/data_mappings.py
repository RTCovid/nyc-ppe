import json
from datetime import datetime
from enum import Enum
from typing import NamedTuple, Dict

from django.core.serializers.json import DjangoJSONEncoder

from ppe import models
from ppe.dataclasses import Item, OrderType
from xlsx_utils import SheetMapping, Mapping


class DataType(str, Enum):
    EDC_PPE = 'edc_ppe_data'


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


def parse_int(inp: str):
    if isinstance(inp, int):
        return inp
    if inp is None:
        return None
    return int(inp)


class SourcingRow(NamedTuple):
    item: Item
    quantity: int

    vendor: str
    delivery_day_1: datetime
    delivery_day_1_quantity: int

    delivery_day_2: datetime
    delivery_day_2_quantity: int

    raw_data: Dict[str, any]

    def __repr__(self):
        fields = self._asdict()
        del fields['raw_data']
        return json.dumps(fields, indent=1, cls=DjangoJSONEncoder)

    def sanity(self):
        delivered_quantity = (self.delivery_day_1_quantity or 0) + (self.delivery_day_2_quantity or 0)
        errors = []
        # lots of data doesn't have delivery dates.
        # if delivered_quantity > self.quantity:
        #    errors.append('Delivery > total')
        # if delivered_quantity < self.quantity:
        #    errors.append(f'Delivery < total {delivered_quantity} < {self.quantity}')
        if self.quantity is None:
            errors.append('Quantity is None')
        return errors

    def to_objects(self):
        errors = self.sanity()
        if errors:
            print(f'Refusing to generate a data model for: {self}. Errors: {errors}')
            return []
        purchase = models.Purchase(
            item=self.item,
            quantity=self.quantity,
            vendor=self.vendor,
            raw_data=self.raw_data,
            data_source=DataType.EDC_PPE,
            order_type=OrderType.Purchase
        )
        deliveries = []
        for day in [1, 2]:
            total = 0
            if getattr(self, f'delivery_day_{day}'):
                quantity = getattr(self, f'delivery_day_{day}_quantity')
                if quantity is None:
                    quantity = self.quantity - total
                    print(f'Warning: Assuming that a null quantity means a full delivery for {self}')
                deliveries.append(
                    models.Delivery(
                        purchase=purchase,
                        delivery_date=getattr(self, f'delivery_day_{day}'),
                        quantity=quantity,
                        data_source=DataType.EDC_PPE
                    )
                )
        return [purchase, *deliveries]


DCAS_DAILY_SOURCING = SheetMapping(
    mappings=[
        Mapping(sheet_column_name='Type  Hierarchy - Critical Asset', obj_column_name='item', proc=asset_name_to_item),
        Mapping(sheet_column_name='Sum of Total Ordered Individual Unit Qty', obj_column_name='quantity',
                proc=parse_int),
        Mapping(sheet_column_name='Expected Delivery Date Day 1', obj_column_name='delivery_day_1', proc=parse_date),
        Mapping(sheet_column_name='Sum of Vendor Delivery Day 1 Estimate LD Qty',
                obj_column_name='delivery_day_1_quantity', proc=parse_int),
        Mapping(sheet_column_name='Expected Delivery Date Day 2', obj_column_name='delivery_day_2', proc=parse_date),
        Mapping(sheet_column_name='Vendor Delivery Day 2 Estimate LD Qty',
                obj_column_name='delivery_day_2_quantity', proc=parse_int),
        Mapping(sheet_column_name='Type  Hierarchy - Vendor', obj_column_name='vendor')
    ],
    include_raw=True,
    obj_constructor=SourcingRow
)
