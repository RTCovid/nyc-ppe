import uuid
from enum import Enum

from django.db import models


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    data_source = models.TextField()

    class Meta:
        abstract = True


def enum2choices(enum):
    return [(v[0], v[0]) for v in enum.__members__.items()]


# tightly control this column to keep the DB clean
class ReporterType(str, Enum):
    faceshield = "faceshield"
    gown = "gown"
    gown_material = "gown_material"


class Purchase(BaseModel):
    item = models.TextField(choices=enum2choices(ReporterType))
