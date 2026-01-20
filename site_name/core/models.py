import uuid

from django.db import models


class BaseUuidModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        # managed = False

    def update_obj(self, data: dict) -> None:
        for attr, value in data.items():
            setattr(self, attr, value)
