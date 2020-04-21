import hashlib
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional, List

import sentry_sdk
from django.contrib.auth.models import User

import xlsx_utils
from ppe.data_mapping.mappers import (
    dcas_make,
    dcas_sourcing,
    inventory_from_facilities,
    hospital_deliveries,
    hospital_demands,
    donations,
    dcas_vents,
)
from ppe.data_mapping.types import DataFile
from ppe.data_mapping.utils import ErrorCollector
from ppe.errors import (
    DataImportError,
    NoMappingForFileError,
    ImportInProgressError,
)
from ppe.models import ImportStatus, DataImport, FacilityDelivery, FailedImport
from xlsx_utils import import_xlsx

ALL_MAPPINGS = [
    dcas_make.SUPPLIERS_AND_PARTNERS,
    dcas_sourcing.DCAS_DAILY_SOURCING,
    dcas_vents.HNH_VENTS,
    inventory_from_facilities.INVENTORY,
    hospital_deliveries.FACILITY_DELIVERIES,
    hospital_demands.WEEKLY_DEMANDS,
    donations.DONATION_DATA,
]


def handle_upload(f, current_as_of: date, user: User) -> DataImport:
    with tempfile.NamedTemporaryFile(
        "w+b", delete=False, suffix=f.name
    ) as upload_target:
        for chunk in f.chunks():
            upload_target.write(chunk)
        upload_target.flush()
        try:
            return smart_import(Path(upload_target.name), user.email, current_as_of)
        except Exception as ex:
            # Capture all upload errors -- we will never 500 the UI
            sentry_sdk.capture_message("Failed upload (see exception)")
            sentry_sdk.capture_exception(ex)
            # reset back to beginning so we can read the file into the DB
            upload_target.seek(0)
            FailedImport(
                data=upload_target.read(),
                file_name=f.name,
                uploaded_by=user,
                current_as_of=current_as_of,
            ).save()
            raise


def import_in_progress(data_file: DataFile):
    return DataImport.objects.filter(data_file=data_file, status=ImportStatus.candidate)


def smart_import(
    path: Path,
    uploader_name: str,
    current_as_of: date,
    overwrite_in_prog: bool = False,
    user_provided_name: Optional[str] = None,
) -> DataImport:
    possible_mappings = xlsx_utils.guess_mapping(path, ALL_MAPPINGS)
    if len(possible_mappings) == 0:
        raise NoMappingForFileError()
    return import_data(
        path,
        possible_mappings,
        current_as_of=current_as_of,
        uploaded_by=uploader_name,
        overwrite_in_prog=overwrite_in_prog,
        user_provided_filename=user_provided_name,
    )


def import_data(
    path: Path,
    mappings: List[xlsx_utils.SheetMapping],
    current_as_of: date,
    user_provided_filename: Optional[str],
    uploaded_by: Optional[str] = None,
    overwrite_in_prog=False,
):
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
        current_as_of=current_as_of,
        data_file=data_file,
        uploaded_by=uploaded_by,
        file_checksum=checksum,
        file_name=user_provided_filename or path.name,
    )
    data_import.save()

    for mapping in mappings:
        try:
            data = import_xlsx(path, mapping, error_collector)
            data = list(data)
            # there are a lot of deliveries, pull them out for bulk import
            deliveries = []
            for item in data:
                try:
                    for obj in item.to_objects(error_collector):
                        obj.source = data_import
                        if isinstance(obj, FacilityDelivery):
                            deliveries.append(obj)
                        else:
                            obj.save()
                except Exception as ex:
                    error_collector.report_error(
                        f"Failure importing row. This is a bug: {ex}"
                    )
                    sentry_sdk.capture_exception(ex)

            FacilityDelivery.objects.bulk_create(deliveries)

        except Exception:
            print(f"Failure importing {path}, mapping: {mapping.sheet_name}")
            raise

    print(f"Errors: ")
    error_collector.dump()
    return data_import


def finalize_import(data_import: DataImport):
    current_active = DataImport.objects.filter(
        data_file=data_import.data_file, status=ImportStatus.active
    )
    if current_active.count() > 1:
        raise DataImportError("Multiple active imports")
    current_active.update(status=ImportStatus.replaced)
    data_import.status = ImportStatus.active
    data_import.save()
