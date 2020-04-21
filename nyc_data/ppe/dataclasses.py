from datetime import datetime, timedelta, date
from enum import Enum

from dataclasses import dataclass

from typing import NamedTuple, Optional, List


class MayoralCategory(str, Enum):
    eye_protection = "Eye Protection"
    ventilators_full_service = "Ventilators - Full Service"
    ventilators_non_full_service = "Ventilators - Non Full Service"
    gloves = "Gloves"
    iso_gowns = "Gowns & Coverings"
    n95_masks = "N95 Masks"
    non_surgical_masks = "Face Coverings"
    other_ppe = "Other PPE"
    surgical_masks = "Surgical Masks"
    body_bags = "Post Mortem Bags"
    other_medical_supplies = "Other Medical Supplies"

    uncategorized = "Uncategorized"

    def display(self):
        return self.value


class Unit(str, Enum):
    each = "each"
    yard = "yard"
    lb = "lb"


class OrderType(str, Enum):
    Purchase = "purchase"
    Make = "make"
    Donation = "donation"


# tightly control this column to keep the DB clean
class Item(str, Enum):
    faceshield = "faceshield"
    gown = "gown"
    gown_material = "gown_material"
    coveralls = "coveralls"
    ponchos = "ponchos"
    scrubs = "scrubs"

    n95_mask_non_surgical = "n95_mask"
    n95_mask_surgical = "n95_mask_surgical"
    kn95_mask = "kn95_mask"
    surgical_mask = "surgical_mask"
    mask_other = "mask_other"

    goggles = "goggles"
    generic_eyeware = "generic_eyeware"

    gloves = "gloves"

    ventilators_full_service = "ventilators_full"
    ventilators_non_full_service = "ventilators_non_full"
    bipap_machines = "bipap_machines"

    ppe_other = "ppe_other"
    unknown = "unknown"

    body_bags = "body_bags"

    def to_mayoral_category(self):
        return ITEM_TO_MAYORAL[self]

    def display(self):
        return ITEM_TO_DISPLAYNAME[self]


class Delivery(NamedTuple):
    quantity: int
    delivery_date: datetime
    item: str
    description: str
    # TODO: probably want to have source info structured
    source: str
    vendor: Optional[str] = None


@dataclass
class Forecast:
    date: str
    demand: int
    existing_supply: int
    additional_supply: int
    inventory: int


class Purchase(NamedTuple):
    order_type: OrderType
    vendor: str

    item: str
    description: str
    quantity: int

    unscheduled_quantity: int

    deliveries: List[Delivery]


class Supplier(str, Enum):
    dcas_donations = "dcas_donations"
    dcas_procurement = "dcas_procurement"
    # stuff like CVD19 Supply, SNS, etc.
    other = "other"


class FacilityType(str, Enum):
    government = "government"
    hospital = "hospital"
    ems = "ems"
    nursing_home = "nursing_home"
    clinic = "clinic"


ITEM_TO_DISPLAYNAME = {
    Item.faceshield: "Face Shields",
    Item.gown: "Gowns",
    Item.gown_material: "Gown Material",
    Item.coveralls: "Coveralls",
    Item.ponchos: "Ponchos",
    Item.scrubs: "Scrubs",
    Item.n95_mask_non_surgical: "Face coverings",
    Item.n95_mask_surgical: "Surgical N95 Masks",
    Item.kn95_mask: "KN95 Masks",
    Item.surgical_mask: "Surgical Masks",
    Item.mask_other: "Other Face Masks",
    Item.goggles: "Goggles",
    Item.gloves: "Gloves",
    Item.generic_eyeware: "Eyeware",
    Item.ventilators_full_service: "Full Service Ventilators",
    Item.ventilators_non_full_service: "Non Full Service Ventilators",
    Item.bipap_machines: "BiPAP Machines",
    Item.ppe_other: "Other PPE",
    Item.unknown: "Other Assets",
    Item.body_bags: "Post Mortem Bags",
}

ITEM_TO_MAYORAL = {
    Item.faceshield: MayoralCategory.eye_protection,
    Item.gown: MayoralCategory.iso_gowns,
    Item.gown_material: MayoralCategory.uncategorized,
    Item.coveralls: MayoralCategory.iso_gowns,
    Item.ponchos: MayoralCategory.other_ppe,
    Item.scrubs: MayoralCategory.other_ppe,
    Item.n95_mask_non_surgical: MayoralCategory.non_surgical_masks,
    Item.n95_mask_surgical: MayoralCategory.n95_masks,
    Item.kn95_mask: MayoralCategory.n95_masks,
    Item.surgical_mask: MayoralCategory.surgical_masks,
    Item.mask_other: MayoralCategory.non_surgical_masks,
    Item.goggles: MayoralCategory.eye_protection,
    Item.gloves: MayoralCategory.gloves,
    Item.generic_eyeware: MayoralCategory.eye_protection,
    Item.ventilators_full_service: MayoralCategory.ventilators_full_service,
    Item.ventilators_non_full_service: MayoralCategory.ventilators_non_full_service,
    # TODO: mayoral category for BiPAP machines
    Item.bipap_machines: MayoralCategory.uncategorized,
    Item.ppe_other: MayoralCategory.other_ppe,
    Item.unknown: MayoralCategory.uncategorized,
    Item.body_bags: MayoralCategory.body_bags,
}


class Period(NamedTuple):
    start: date
    end: date

    @classmethod
    def last_week(cls):
        return Period(datetime.today() - timedelta(days=6), datetime.today())

    def inclusive_length(self):
        return self.end - self.start + timedelta(days=1)

    def exclusive_length(self):
        return self.end - self.start
