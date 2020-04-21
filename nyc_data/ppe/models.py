import tempfile
import uuid
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Dict

from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import Sum, Max, QuerySet

import ppe.dataclasses as dc
from ppe.data_mapping.types import DataFile


def enum2choices(enum):
    return [(v[0], v[0]) for v in enum.__members__.items()]


def ChoiceField(enum, default=None):
    return models.TextField(
        choices=[(v[0], v[0]) for v in enum.__members__.items()], default=default
    )


class ImportStatus(str, Enum):
    active = "active"
    replaced = "replaced"
    candidate = "candidate"
    cancelled = "cancelled"


class DataImport(models.Model):
    import_date = models.DateTimeField(auto_now_add=True, db_index=True)
    status = ChoiceField(ImportStatus)
    data_file = ChoiceField(DataFile)

    current_as_of = models.DateField(null=True)

    uploaded_by = models.TextField(blank=True)
    file_checksum = models.TextField()
    file_name = models.TextField()
    file = models.FileField

    @classmethod
    def sanity(cls):
        # for each data_source, at most 1 active
        for _, src in DataFile.__members__.items():
            ct = DataImport.objects.filter(
                data_file=src, status=ImportStatus.active
            ).count()
            if ct > 1:
                print(f"Something is weird, more than one active object for {src}")
                return False
        return True

    def cancel(self):
        self.status = ImportStatus.cancelled

    def display(self):
        return f'File uploaded {self.import_date.strftime("%d/%m/%y")} by {self.uploaded_by or "unknown"}. Filename: {self.file_name}'

    def compute_delta(self):
        if not self.sanity():
            raise Exception(
                "Can't compute a delta. Something is horribly wrong in the DB"
            )
        if self.status != ImportStatus.candidate:
            raise Exception("Can only compute a delta on a candidate import")

        active_import = DataImport.objects.filter(
            status=ImportStatus.active, data_file=self.data_file
        ).first()

        if active_import:
            active_objects = active_import.imported_objects()
        else:
            active_objects = {}

        new_objects = {
            k: set(objs).difference(active_objects.get(k))
            if k in active_objects.keys()
            else set(objs)
            for k, objs in self.imported_objects().items()
        }

        return UploadDelta(
            previous=active_import,
            active_stats={
                tpe.__name__: len(objs) for (tpe, objs) in active_objects.items()
            },
            candidate_stats={
                tpe.__name__: len(objs)
                for (tpe, objs) in self.imported_objects().items()
            },
            new_objects=new_objects,
        )

    def imported_objects(self):
        return {
            tpe: tpe.objects.prefetch_related("source").filter(source=self)
            for tpe in [
                ScheduledDelivery,
                Inventory,
                Purchase,
                FacilityDelivery,
                Demand,
            ]
        }


class UploadDelta(NamedTuple):
    previous: DataImport
    active_stats: Dict[str, int]
    candidate_stats: Dict[str, int]

    new_objects: Dict[str, any]


def current_as_of(qs: QuerySet):
    if qs.count() == 0:
        return "Unknown"
    return qs.first().source.current_as_of or "Unknown"


class ImportedDataModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    source = models.ForeignKey(DataImport, on_delete=models.CASCADE)

    @classmethod
    def active(cls):
        return cls.objects.prefetch_related("source").filter(
            source__status=ImportStatus.active
        )

    def check_cached(self, field):
        """
        Helper wrapper to log a warning if a related field isn't cached
        Usage:

            def item(self):
                self.check_cached('purchase').item

        :param field: field name (string)
        :return:
        """
        cached = getattr(self.__class__, field).field.get_cached_value(
            self, default=None
        )
        if cached is None:
            print(f"Warning: {field} not cached on {self}")
        return getattr(self, field)

    class Meta:
        abstract = True


class Purchase(ImportedDataModel):
    order_type = ChoiceField(dc.OrderType)

    item = ChoiceField(dc.Item)
    description = models.TextField(blank=True)
    quantity = models.IntegerField()
    unit = ChoiceField(dc.Unit, default=dc.Unit.each)

    received_quantity = models.IntegerField(default=0)

    vendor = models.TextField()
    cost = models.IntegerField(null=True)
    donation_date = models.DateField(null=True, blank=True, default=None)
    comment = models.TextField(blank=True)

    raw_data = JSONField()

    @property
    def total_deliveries(self):
        # WARNING: I this doesn't seem to be prefetched.
        return self.deliveries.aggregate(Sum("quantity"))["quantity__sum"]

    @property
    def complete(self):
        return self.received_quantity == self.quantity

    @property
    def unscheduled_quantity(self):
        if self.received_quantity == self.quantity:
            return 0
        else:

            return self.quantity - (self.total_deliveries or 0)


class Inventory(ImportedDataModel):
    item = ChoiceField(dc.Item)
    quantity = models.IntegerField()
    as_of = models.DateField()

    raw_data = JSONField()

    @classmethod
    def as_of_latest(cls):
        return super().active().aggregate(Max("as_of"))["as_of__max"]

    @classmethod
    def active(cls):
        return super().active().filter(as_of=cls.as_of_latest())


class FailedImport(models.Model):
    data = models.BinaryField(blank=False)
    file_name = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    current_as_of = models.DateField()
    fixed = models.BooleanField(default=False)

    def retry(self):
        with tempfile.NamedTemporaryFile(
            "w+b", delete=False, suffix=self.file_name
        ) as f:
            f.write(self.data)
            f.flush()

            from ppe.data_import import smart_import, finalize_import

            import_obj = smart_import(
                path=Path(f.name),
                uploader_name=self.uploaded_by.username,
                current_as_of=self.current_as_of,
                user_provided_name=self.file_name,
                overwrite_in_prog=True
            )
            finalize_import(import_obj)
            self.fixed = True
            self.save()


class ScheduledDelivery(ImportedDataModel):
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="deliveries"
    )
    delivery_date = models.DateField(null=True)
    quantity = models.IntegerField()

    @property
    def item(self):
        return self.check_cached("purchase").item

    @property
    def description(self):
        return self.check_cached("purchase").description

    @property
    def vendor(self):
        return self.check_cached("purchase").vendor

    def to_dataclass(self):
        return dc.Delivery(
            item=dc.Item(self.purchase.item).display(),
            description=self.purchase.description,
            delivery_date=self.delivery_date,
            quantity=self.quantity,
            vendor=self.purchase.vendor,
            source=self.source.display(),
        )


class InboundReceipt(ImportedDataModel):
    date_received = models.DateTimeField()
    supplier = ChoiceField(dc.Supplier)
    description = models.TextField()
    quantity = models.IntegerField()
    inbound_id = models.TextField()
    item_id = models.TextField()
    item = ChoiceField(dc.Item)


class Facility(ImportedDataModel):
    name = models.TextField()
    tpe = ChoiceField(dc.FacilityType)


class FacilityDelivery(ImportedDataModel):
    date = models.DateField()
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    item = ChoiceField(dc.Item)
    quantity = models.IntegerField()


class Demand(ImportedDataModel):
    """Real demand data from NYC"""

    item = ChoiceField(dc.Item)
    demand = models.IntegerField()
    # both start and end are inclusive
    start_date = models.DateField()
    end_date = models.DateField()


class Hospital(ImportedDataModel):
    # TODO: need to figure out what resolution is needed. Could bring in the full geocoding hospital
    # model from covidhospitalstatus
    name = models.TextField()


class Need(ImportedDataModel):
    item = models.TextField(choices=enum2choices(dc.Item))
    date = models.DateField()

    quantity = models.IntegerField()
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)

    satisfied = models.BooleanField()
