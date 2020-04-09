import uuid

from django.contrib.postgres.fields import JSONField
from django.db import models

import ppe.dataclasses as dc
from ppe.data_mappings import DataType


def enum2choices(enum):
    return [(v[0], v[0]) for v in enum.__members__.items()]


def ChoiceField(enum, default=None):
    return models.TextField(choices=[(v[0], v[0]) for v in enum.__members__.items()], default=default)


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    # TODO: why isn't this getting validated
    data_source = ChoiceField(DataType)
    # Keep track of data that's been replaced
    replaced = models.BooleanField(default=False)

    class Meta:
        abstract = True


class Purchase(BaseModel):
    order_type = ChoiceField(dc.OrderType)
    item = ChoiceField(dc.Item)
    quantity = models.IntegerField()
    unit = ChoiceField(dc.Unit, default=dc.Unit.each)

    vendor = models.TextField()
    cost = models.IntegerField(null=True)

    raw_data = JSONField()


class Delivery(BaseModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    delivery_date = models.DateField(null=True)
    quantity = models.IntegerField()


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
