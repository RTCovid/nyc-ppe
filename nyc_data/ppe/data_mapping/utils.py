from datetime import datetime

from ppe.dataclasses import Item


class ErrorCollector:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def __len__(self):
        return len(self.errors) + len(self.warnings)

    def report_error(self, err: str):
        self.errors.append(err)

    def report_warning(self, warning: str):
        self.warnings.append(warning)

    def dump(self):
        print("\n".join(set(self.errors)))
        print("\n".join(set(self.warnings)))

    def __repr__(self):
        return f"{len(self.errors)} errors and {len(self.warnings)} warnings"


def asset_name_to_item(asset_name: str, error_collector: ErrorCollector) -> Item:
    if asset_name is None:
        error_collector.report_error("Null asset name")
        return Item.unknown
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
        "Body Bags": Item.body_bags,
        "Face Masks": Item.mask_other,
        "Post Mortem Bags": Item.body_bags,
        "N95 Respirators": Item.n95_mask_surgical,
        "BiPap": Item.bipap_machines,
        "Misc": Item.ppe_other,
        "Multipurpose PPE": Item.ppe_other,
    }
    match = mapping.get(asset_name.strip())
    if match is not None:
        return match
    error_collector.report_warning(f"Unknown type: {asset_name}")
    return Item.unknown


def parse_date(date: any, error_collector: ErrorCollector):
    formats = [
        ("%m/%d/%Y", lambda x: x),  # 04/10/2020
        ("%m/%d/%y", lambda x: x),  # 04/10/20
        ("%Y-%m-%d", lambda x: x),  # 2020-04-10
        ("%d-%b", lambda d: d.replace(year=2020)),  # 30-Apr
        ("%m/%d", lambda d: d.replace(year=2020)),  # 4/15
        ("%m-%d", lambda d: d.replace(year=2020)),  # 04-13
        ("%m-%d-%Y", lambda x: x),
    ]
    if isinstance(date, str):
        date = date.strip()
        match = []
        for fmt, mapper in formats:
            try:
                match.append(mapper(datetime.strptime(date, fmt)))
            except ValueError:
                pass
        if len(set(match)) > 1:
            error_collector.report_error(f"Ambiguous date! {date}")
        elif len(set(match)) == 1:
            return match[0]
        else:
            error_collector.report_error(f"Unknown date format: {date}")
            return None
    elif isinstance(date, datetime):
        return date
    else:
        return None


def parse_int_or_zero(inp: str, error_collector: ErrorCollector):
    return parse_int(inp, error_collector) or 0


def parse_int(inp: str, error_collector: ErrorCollector):
    if isinstance(inp, int):
        return inp
    if inp is None:
        return None
    try:
        return int(inp)
    except ValueError:
        # Maybe there's a unit or some other crap
        error_collector.report_error(
            f"Can't parse {inp}. Returning None for now [TODO]"
        )
        return None


def parse_bool(inp: str, error_collector: ErrorCollector):
    # TODO: would probably be useful to show more than just true/false
    if inp is None:
        error_collector.report_error('Bool input was None')
        return None
    inp = inp.lower().strip()
    if inp in {"y", "yes"}:
        return True
    elif inp in {"n", "no"}:
        return False
    else:
        error_collector.report_error(f"Failed to parse bool: `{inp}`")


def parse_string_or_none(inp: str, error_collector: ErrorCollector):
    if inp and len(inp):
        return inp
    else:
        return "None"
