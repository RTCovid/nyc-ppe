from enum import Enum


class MayoralCategory(str, Enum):
    eye_protection = 'Eye Protection'
    ventilators_full_service = 'Ventilators - Full Service'
    ventilators_non_full_service = 'Ventilators - Non Full Service'
    gloves = 'Gloves'
    iso_gowns = 'ISO Gowns'
    n95_masks = 'N95 Masks'
    non_surgical_masks = 'Non - Surgical Masks'
    other_ppe = 'Other PPE'
    surgical_masks = 'Surgical Masks'
    other_medical_supplies = 'Other Medical Supplies'


class Unit(str, Enum):
    each = "each"
    yard = "yard"
    lb = "lb"


class OrderType(str, Enum):
    Purchase = 'purchase'
    Make = 'make'


# tightly control this column to keep the DB clean
class Item(str, Enum):
    faceshield = "faceshield"
    gown = "gown"
    gown_material = "gown_material"
    coveralls = "coveralls"

    n95_mask_non_surgical = "n95_mask"
    n95_mask_surgical = "n95_mask_surgical"
    kn95_mask = "kn95_mask"
    surgical_mask = "surgical_mask"
    mask_other = "mask_other"

    goggles = "goggles"

    gloves = "gloves"

    ventilators_full_service = "ventilators_full"
    ventilators_non_full_service = "ventilators_non_full"

    ppe_other = 'ppe_other'
    unknown = 'unknown'
