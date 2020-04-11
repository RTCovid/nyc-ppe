import uuid
from enum import Enum

from django.contrib.postgres.fields import JSONField
from django.db import models

import ppe.dataclasses as dc
from ppe.data_mappings import DataSource


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


class DataImport(models.Model):
    import_date = models.DateTimeField(auto_now_add=True, db_index=True)
    status = ChoiceField(ImportStatus)
    data_source = ChoiceField(DataSource)

    uploaded_by = models.TextField(blank=True)
    file_checksum = models.TextField()
    file_name = models.TextField()

    @classmethod
    def sanity(cls):
        # for each data_source, at most 1 active
        for _, src in DataSource.__members__.item():
            ct = DataImport.objects.filter(data_source=src, status=ImportStatus.active).count()
            if ct > 1:
                print(f'Something is weird, more than one active object for {src}')
                return False
        return True

    def display(self):
        return f'File uploaded {self.import_date.strftime("%d/%m/%y")} by {self.uploaded_by or "unknown"}. Filename: {self.file_name}'


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    source = models.ForeignKey(DataImport, on_delete=models.CASCADE)

    @classmethod
    def active(cls):
        return cls.objects.prefetch_related('source').filter(source__status=ImportStatus.active)

    class Meta:
        abstract = True


class Purchase(BaseModel):
    order_type = ChoiceField(dc.OrderType)

    item = ChoiceField(dc.Item)
    description = models.TextField(blank=True)
    quantity = models.IntegerField()
    unit = ChoiceField(dc.Unit, default=dc.Unit.each)

    vendor = models.TextField()
    cost = models.IntegerField(null=True)

    raw_data = JSONField()


class Inventory(BaseModel):
    item = ChoiceField(dc.Item)
    quantity = models.IntegerField()

    raw_data = JSONField()


class Delivery(BaseModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    delivery_date = models.DateField(null=True)
    quantity = models.IntegerField()

    def to_dataclass(self):
        return dc.Delivery(
            item=dc.Item(self.purchase.item).display(),
            description=self.purchase.description,
            delivery_date=self.delivery_date,
            quantity=self.quantity,
            vendor=self.purchase.vendor,
            source=self.source.display()
        )


class Hospital(BaseModel):
    # TODO: need to figure out what resolution is needed. Could bring in the full geocoding hospital
    # model from covidhospitalstatus
    name = models.TextField()


class Need(BaseModel):
    item = models.TextField(choices=enum2choices(dc.Item))
    date = models.DateField()

    quantity = models.IntegerField()
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)

    satisfied = models.BooleanField()
