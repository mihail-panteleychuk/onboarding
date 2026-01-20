from datetime import datetime
from enum import Enum

from django.db import models


class ValueType(Enum):
    TYPE_STR = 1
    TYPE_INT = 2
    TYPE_FLOAT = 3
    TYPE_DATE = 4
    TYPE_DATETIME = 5
    TYPE_BOOLEAN = 6


ValueTypeMapping = {
    ValueType.TYPE_STR.value: str,
    ValueType.TYPE_INT.value: int,
    ValueType.TYPE_FLOAT.value: float,
    ValueType.TYPE_DATE.value: lambda x: datetime.strptime(x, "%Y-%m-%d"),
    ValueType.TYPE_DATETIME.value: lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S"),
    ValueType.TYPE_BOOLEAN.value: lambda x: x.lower() in ["true", "yes", "1"],
}


class SettingValueTypes(models.IntegerChoices):
    TYPE_STR = ValueType.TYPE_STR.value, "Text"
    TYPE_INT = ValueType.TYPE_INT.value, "Integer number"
    TYPE_FLOAT = ValueType.TYPE_FLOAT.value, "Float point number"
    TYPE_DATE = ValueType.TYPE_DATE.value, "Date: YYYY-MM-DD"
    TYPE_DATETIME = ValueType.TYPE_DATETIME.value, "Datetime: YYYY-MM-DD HH:MM:SS"
    TYPE_BOOLEAN = ValueType.TYPE_BOOLEAN.value, "Boolean: true or false"


class WhiteListPatternType(models.TextChoices):
    DOMAIN = "domain", "Domain"
    FULL = "full", "Full"
