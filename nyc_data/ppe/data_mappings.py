import json
from abc import ABC, abstractmethod, ABCMeta
from datetime import datetime, timedelta
from enum import Enum
from typing import NamedTuple, Dict, Optional, NamedTupleMeta

from django.core.serializers.json import DjangoJSONEncoder

from ppe import models
from ppe.dataclasses import Item, OrderType
from xlsx_utils import SheetMapping, Mapping


class DataSource(str, Enum):
    EDC_PPE = "edc_ppe_data"
    EDC_MAKE = "edc_suppliers_partners"
    INVENTORY = "inventory"


class ImportedNamedTuple(ABCMeta, NamedTupleMeta):
    pass


def repr_no_raw(obj):
    fields = obj._asdict()
    del fields["raw_data"]
    return json.dumps(fields, indent=1, cls=DjangoJSONEncoder)


class ImportedRow(metaclass=ImportedNamedTuple):
    @abstractmethod
    def to_objects(self):
        pass

    @abstractmethod
    def __repr__(self):
        pass


def asset_name_to_item(asset_name: str) -> Item:
    mapping = {
        "KN95 Masks": Item.kn95_mask,
        "Face Masks-Other": Item.mask_other,
        "Surgical Grade N95s Masks": Item.n95_mask_surgical,
        "Non-Surgical Grade N95s Masks": Item.n95_mask_non_surgical,
        "Isolation Gowns": Item.gown,
        "Gowns": Item.gown,
        "Materials for Gowns": Item.gown_material,
        "Coveralls": Item.coveralls,
        "Non Full Service Ventilators": Item.ventilators_non_full_service,
        "Face Coverings-Non Medical": Item.mask_other,
        "Goggles": Item.goggles,
        "Other PPE, Healthcare": Item.ppe_other,
        "Full Service Ventilators": Item.ventilators_full_service,
        "Face Shields": Item.faceshield,
        "Faceshield": Item.faceshield,
        "Face Shield": Item.faceshield,
        "Gloves": Item.gloves,
        "Surgical Masks": Item.surgical_mask,
        "N95": Item.n95_mask_surgical,
        "Facemasks": Item.mask_other,
        "Eyewear": Item.generic_eyeware,
        "Vents": Item.ventilators_full_service,
        "BiPAP Machines": Item.bipap_machines,
        "Body Bags": Item.body_bags
    }
    match = mapping.get(asset_name)
    if match is not None:
        return match
    print(f"Unknown type: {asset_name}")
    return Item.unknown


def parse_date(date: any):
    formats = [
        ("%m/%d/%Y", lambda x: x),  # 04/10/2020
        ("%d-%b", lambda d: d.replace(year=2020)),
        ("%m/%d", lambda d: d.replace(year=2020)),
    ]
    if isinstance(date, str):
        for fmt, mapper in formats:
            try:
                return mapper(datetime.strptime(date, fmt))
            except ValueError:
                pass
        print(f"Unknown date format: {date}")
        return None
    elif isinstance(date, datetime):
        return date
    else:
        return None


def parse_int(inp: str):
    if isinstance(inp, int):
        return inp
    if inp is None:
        return None
    try:
        return int(inp)
    except ValueError:
        # Maybe there's a unit or some other crap
        print(f"Can't parse {inp}. Returning None for now [TODO]")
        return None


class SourcingRow(ImportedRow, NamedTuple):
    item: Item
    description: str
    quantity: int

    vendor: str
    delivery_day_1: datetime
    delivery_day_1_quantity: int

    delivery_day_2: datetime
    delivery_day_2_quantity: int

    raw_data: Dict[str, any]

    def __repr__(self):
        # return super().repr_no_raw()
        return repr_no_raw(self)

    def sanity(self):
        delivered_quantity = (self.delivery_day_1_quantity or 0) + (
                self.delivery_day_2_quantity or 0
        )
        errors = []
        # lots of data doesn't have delivery dates.
        # if delivered_quantity > self.quantity:
        #    errors.append('Delivery > total')
        # if delivered_quantity < self.quantity:
        #    errors.append(f'Delivery < total {delivered_quantity} < {self.quantity}')
        if self.quantity is None:
            errors.append("Quantity is None")
        return errors

    def to_objects(self):
        errors = self.sanity()
        if errors:
            print(f"Refusing to generate a data model for: {self}. Errors: {errors}")
            return []
        purchase = models.Purchase(
            item=self.item,
            quantity=self.quantity,
            vendor=self.vendor,
            raw_data=self.raw_data,
            order_type=OrderType.Purchase,
            description=self.description
        )
        deliveries = []
        for day in [1, 2]:
            total = 0
            if getattr(self, f"delivery_day_{day}"):
                quantity = getattr(self, f"delivery_day_{day}_quantity")
                if quantity is None:
                    quantity = self.quantity - total
                    print(
                        f"Warning: Assuming that a null quantity means a full delivery for {self}"
                    )
                deliveries.append(
                    models.Delivery(
                        purchase=purchase,
                        delivery_date=getattr(self, f"delivery_day_{day}"),
                        quantity=quantity,
                    )
                )
        return [purchase, *deliveries]


DCAS_DAILY_SOURCING = SheetMapping(
    sheet_name="Data - Daily DCAS Sourcing",
    mappings=[
        Mapping(
            sheet_column_name="Type  Hierarchy - Critical Asset",
            obj_column_name="item",
            proc=asset_name_to_item,
        ),
        Mapping(
            sheet_column_name='Type  Hierarchy - Description',
            obj_column_name='description',
        ),
        Mapping(
            sheet_column_name="Sum of Total Ordered Individual Unit Qty",
            obj_column_name="quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Expected Delivery Date Day 1",
            obj_column_name="delivery_day_1",
            proc=parse_date,
        ),
        Mapping(
            sheet_column_name="Sum of Vendor Delivery Day 1 Estimate LD Qty",
            obj_column_name="delivery_day_1_quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Expected Delivery Date Day 2",
            obj_column_name="delivery_day_2",
            proc=parse_date,
        ),
        Mapping(
            sheet_column_name="Vendor Delivery Day 2 Estimate LD Qty",
            obj_column_name="delivery_day_2_quantity",
            proc=parse_int,
        ),
        Mapping(sheet_column_name="Type  Hierarchy - Vendor", obj_column_name="vendor"),
    ],
    include_raw=True,
    obj_constructor=SourcingRow,
)


class MakeRow(ImportedRow, NamedTuple):
    item: Item
    quantity: int
    raw_data: Dict[str, any]
    delivery_date: Optional[datetime]
    # used to handle stuff like `TBD` and `weekly until 5/30`
    raw_date: Optional[str]

    vendor: Optional[str]

    def __repr__(self):
        return repr_no_raw(self)

    def sanity(self):
        if self.quantity is None:
            return ["Quantity is none"]

    def to_objects(self):
        errors = self.sanity()
        if errors:
            print(f"Refusing to generate a data model for: {self}. Errors: {errors}")
            return []
        purchase = models.Purchase(
            item=self.item,
            quantity=self.quantity,
            vendor=self.vendor,
            raw_data=self.raw_data,
            order_type=OrderType.Make,
        )
        dates = []
        if self.delivery_date:
            dates.append(self.delivery_date)
        elif "weekly" in self.raw_date:
            import re

            date_str = re.sub(r"[a-zA-Z ]+", "", self.raw_date).strip()
            end_date = parse_date(date_str)
            if end_date:
                dates = []
                while end_date > datetime.today():
                    dates.append(end_date)
                    end_date -= timedelta(weeks=1)

        delivery = [
            models.Delivery(
                purchase=purchase,
                delivery_date=date,
                quantity=self.quantity,
            )
            for date in dates
        ]

        return [purchase, *delivery]


SUPPLIERS_AND_PARTNERS = SheetMapping(
    sheet_name="EDC Suppliers & Partners",
    mappings=[
        Mapping(
            sheet_column_name="Supply / Service",
            obj_column_name="item",
            proc=asset_name_to_item,
        ),
        Mapping(
            sheet_column_name="Number of Units",
            obj_column_name="quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Delivery Date",
            obj_column_name="delivery_date",
            proc=parse_date,
        ),
        Mapping(sheet_column_name="Delivery Date", obj_column_name="raw_date"),
        Mapping(
            sheet_column_name="Counterparty Name (for procurement)",
            obj_column_name="vendor",
        ),
    ],
    include_raw=True,
    obj_constructor=MakeRow,
)


class InventoryRow(ImportedRow, NamedTuple):
    raw_data: Dict[str, any]
    item: Item
    quantity: int

    def to_objects(self):
        return [
            models.Inventory(
                item=self.item,
                raw_data=self.raw_data,
                quantity=self.quantity,
            )
        ]

    def __repr__(self):
        return repr_no_raw(self)


INVENTORY = SheetMapping(
    sheet_name='InventoryHand',
    mappings=[
        Mapping(
            sheet_column_name="Item",
            obj_column_name="item",
            proc=asset_name_to_item,
        ),
        Mapping(
            sheet_column_name="CITY",
            obj_column_name="quantity",
            proc=parse_int
        )
    ],
    include_raw=True,
    obj_constructor=InventoryRow
)
