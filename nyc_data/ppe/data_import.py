import collections
import dataclasses as dc
import hashlib
from pathlib import Path
from typing import Optional

from ppe.data_mappings import DataSource
from ppe import data_mappings
from ppe.models import Purchase, Delivery, Inventory, ImportStatus, DataImport
from xlsx_utils import import_xlsx

mappings = {
    DataSource.EDC_MAKE: data_mappings.SUPPLIERS_AND_PARTNERS,
    DataSource.INVENTORY: data_mappings.INVENTORY,
    DataSource.EDC_PPE: data_mappings.DCAS_DAILY_SOURCING
}


class DataImportError(Exception):
    pass


def import_in_progress(data_source: DataSource):
    return DataImport.objects.filter(data_source=data_source, status=ImportStatus.candidate)


def import_data(path: Path, data_source: DataSource, uploaded_by: Optional[str] = None, overwrite_in_prog=False):
    in_progress = import_in_progress(data_source)

    if in_progress.count() > 0:
        if overwrite_in_prog:
            in_progress.update(status=ImportStatus.replaced)
        else:
            raise DataImportError(
                f"Can't import data -- there is already an import in progress ({in_progress.first().import_date})")

    with open(path, 'rb') as f:
        checksum = hashlib.sha256(f.read())

    uploaded_by = uploaded_by or ''

    mapping = mappings[data_source]
    data = import_xlsx(path, mapping.sheet_name, mapping)
    data = list(data)
    obj_types = {Purchase, Delivery, Inventory}
    num_active_objects = {
        obj_type.__name__: obj_type.objects.prefetch_related('source').filter(
            source__status=ImportStatus.active, source__data_source=data_source).count()
        for obj_type in obj_types
    }
    import_stats = collections.defaultdict(lambda: 0)
    data_import = DataImport(
        status=ImportStatus.candidate,
        data_source=data_source,
        uploaded_by=uploaded_by,
        file_checksum=checksum
    )
    data_import.save()
    for item in data:
        for obj in item.to_objects():
            import_stats[obj.__class__.__name__] += 1
            obj.source = data_import
            obj.save()
    print('Before: ', num_active_objects)
    print('Candidates: ', dict(import_stats))
    return data_import


def complete_import(data_import: DataImport):
    current_active = DataImport.objects.filter(data_source=data_import.data_source, status=ImportStatus.active)
    if current_active.count() > 1:
        raise DataImportError('Multiple active imports')
    current_active.update(status=ImportStatus.replaced)
    data_import.status = ImportStatus.active
    data_import.save()


def full_import(path: Path, data_source: DataSource, overwrite_in_prog: bool = False):
    data_import = import_data(path, data_source, overwrite_in_prog=overwrite_in_prog)
    complete_import(data_import)
