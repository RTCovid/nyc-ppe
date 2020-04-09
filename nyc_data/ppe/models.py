import uuid

from django.contrib.postgres.fields import JSONField
from django.db import models

from ppe.dataclasses import Item, Unit


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    data_source = models.TextField()

    class Meta:
        abstract = True


def enum2choices(enum):
    return [(v[0], v[0]) for v in enum.__members__.items()]


class Purchase(BaseModel):
    item = models.TextField(choices=enum2choices(Item))
    quantity = models.IntegerField()
    unit = models.TextField(choices=enum2choices(Unit), default=Unit.each)

    delivery_date = models.DateField(null=True)

    cost = models.IntegerField()

    raw_data = JSONField()

    counterparty = models.TextField()

    delivery_to = models.TextField()


class Hospital(BaseModel):
    # TODO: need to figure out what resolution is needed. Could bring in the full geocoding hospital
    # model from covidhospitalstatus
    name = models.TextField()


class Need(BaseModel):
    item = models.TextField(choices=enum2choices(Item))
    date = models.DateField()

    quantity = models.IntegerField()
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)

    satisfied = models.BooleanField()
