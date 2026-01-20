from datetime import datetime
from enum import Enum

from django.db import models


class ValueType(Enum):
    TYPE_STR = 1, str
    TYPE_INT = 2, int
    TYPE_FLOAT = 3, float
    TYPE_DATE = 4, datetime  # TODO: use datetime.date
    TYPE_DATETIME = 5, datetime


class SettingValueTypes(models.TextChoices):
    TYPE_STR = (ValueType.TYPE_STR.value, "Text")
    TYPE_INT = (ValueType.TYPE_INT.value, "Integer number")
    TYPE_FLOAT = (ValueType.TYPE_FLOAT.value, "Float point number")
    TYPE_DATE = (ValueType.TYPE_DATE.value, "Date: YYYY-MM-DD")
    TYPE_DATETIME = (ValueType.TYPE_DATETIME.value, "Datetime: YYYY-MM-DD HH:MM:SS")


class WhiteListPatternType(models.TextChoices):
    DOMAIN = "domain", "Domain"
    FULL = "full", "Full"
