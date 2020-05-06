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


NAME_ITEM_MAPPING = {
    "bipap": Item.bipap_machines,
    "bipapmachines": Item.bipap_machines,
    "bodybags": Item.body_bags,
    "coveralls": Item.coveralls,
    "eyewear": Item.generic_eyeware,
    "facecoverings-nonmedical": Item.mask_other,
    "facemasks": Item.mask_other,
    "facemasks-other": Item.mask_other,
    "faceshield": Item.faceshield,
    "faceshields": Item.faceshield,
    "fullserviceventilators": Item.ventilators_full_service,
    "gloves": Item.gloves,
    "gloves-latex": Item.gloves,
    "swabkit": Item.swab_kit,
    "goggles": Item.goggles,
    "gowns": Item.gown,
    "isolationgowns": Item.gown,
    "isogowns": Item.gown,
    "kn95masks": Item.kn95_mask,
    "materialsforgowns": Item.gown_material,
    "misc": Item.ppe_other,
    "multipurposeppe": Item.ppe_other,
    "n95": Item.n95_mask_surgical,
    "n95respirators": Item.n95_mask_surgical,
    "n95respiratormasks": Item.n95_mask_surgical,
    "non-surgicalgraden95smasks": Item.n95_mask_non_surgical,
    "nonfullserviceventilators": Item.ventilators_non_full_service,
    "otherppe,healthcare": Item.ppe_other,
    "postmortembags": Item.body_bags,
    "surgicalgraden95smasks": Item.n95_mask_surgical,
    "surgicalmasks": Item.surgical_mask,
    "vents": Item.ventilators_full_service,
    "ponchos": Item.ponchos,
    "other": Item.unknown,
}


def asset_name_to_item(asset_name: str, error_collector: ErrorCollector) -> Item:
    if asset_name is None:
        error_collector.report_error("Null asset name")
        return Item.unknown
    match = NAME_ITEM_MAPPING.get(asset_name.lower().replace(" ", ""))
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
        error_collector.report_error("Bool input was None")
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
