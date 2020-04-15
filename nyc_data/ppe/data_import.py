import hashlib
import tempfile
from pathlib import Path
from typing import Optional, List

import xlsx_utils
from ppe.data_mapping.mappers import (
    dcas_make,
    dcas_sourcing,
    inventory_from_facilities,
    hospital_deliveries,
    hospital_demands,
)
from ppe.data_mapping.types import DataFile
from ppe.data_mapping.utils import ErrorCollector
from ppe.errors import DataImportError, NoMappingForFileError, PartialFile, ImportInProgressError
from ppe.models import (
    ImportStatus,
    DataImport,
    FacilityDelivery,
)
from xlsx_utils import import_xlsx

ALL_MAPPINGS = [
    dcas_make.SUPPLIERS_AND_PARTNERS,
    dcas_sourcing.DCAS_DAILY_SOURCING,
    inventory_from_facilities.INVENTORY,
    hospital_deliveries.FACILITY_DELIVERIES,
    hospital_demands.WEEKLY_DEMANDS,
]


def handle_upload(f, uploader_name: str) -> DataImport:
    with tempfile.NamedTemporaryFile(
        "w+b", delete=False, suffix=f.name
    ) as upload_target:
        for chunk in f.chunks():
            upload_target.write(chunk)
        upload_target.flush()
        return smart_import(Path(upload_target.name), uploader_name)


def import_in_progress(data_file: DataFile):
    return DataImport.objects.filter(data_file=data_file, status=ImportStatus.candidate)


def smart_import(
    path: Path, uploader_name: str, overwrite_in_prog: bool = False
) -> DataImport:
    possible_mappings = xlsx_utils.guess_mapping(path, ALL_MAPPINGS)
    if len(possible_mappings) == 0:
        raise NoMappingForFileError()
    return import_data(path, possible_mappings, uploader_name, overwrite_in_prog)


def import_data(
    path: Path,
    mappings: List[xlsx_utils.SheetMapping],
    uploaded_by: Optional[str] = None,
    overwrite_in_prog=False,
):
    df = mappings[0].data_file
    if len([m for m in ALL_MAPPINGS if m.data_file == df]) != len(mappings):
        raise PartialFile("Importing a file, but only got one of the expected sheets")
    error_collector = ErrorCollector()
    data_file = {mapping.data_file for mapping in mappings}
    if len(data_file) != 1:
        raise ImportError(
            "Something is wrong, can't import from two different files..."
        )
    data_file = mappings[0].data_file
    in_progress = import_in_progress(data_file)

    if in_progress.count() > 0:
        if overwrite_in_prog:
            in_progress.update(status=ImportStatus.replaced)
        else:
            raise ImportInProgressError(in_progress.first().id)

    with open(path, "rb") as f:
        checksum = hashlib.sha256(f.read())

    uploaded_by = uploaded_by or ""
    data_import = DataImport(
        status=ImportStatus.candidate,
        data_file=data_file,
        uploaded_by=uploaded_by,
        file_checksum=checksum,
        file_name=path.name,
    )
    data_import.save()

    for mapping in mappings:
        try:
            data = import_xlsx(path, mapping, error_collector)
            data = list(data)
            deliveries = []
            demands = []
            for item in data:
                for obj in item.to_objects(error_collector):
                    obj.source = data_import
                    if isinstance(obj, FacilityDelivery):
                        deliveries.append(obj)
                    else:
                        obj.save()

            FacilityDelivery.objects.bulk_create(deliveries)

        except Exception:
            print(f"Failure importing {path}, mapping: {mapping.sheet_name}")
            raise

    print(f"Errors: ")
    error_collector.dump()
    return data_import


def complete_import(data_import: DataImport):
    current_active = DataImport.objects.filter(
        data_file=data_import.data_file, status=ImportStatus.active
    )
    if current_active.count() > 1:
        raise DataImportError("Multiple active imports")
    current_active.update(status=ImportStatus.replaced)
    data_import.status = ImportStatus.active
    data_import.save()
