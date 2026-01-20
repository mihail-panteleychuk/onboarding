from datetime import date, datetime
from typing import Union

from django.db import models
from django.utils.translation import gettext_lazy as _

from site_name.admin_panel.constants import SettingValueTypes, ValueType, WhiteListPatternType
from site_name.core.models import BaseUuidModel


class Settings(BaseUuidModel):
    name = models.CharField(max_length=128, unique=True)
    value = models.CharField(max_length=128)
    value_type = models.IntegerField(choices=SettingValueTypes.choices, default=1)
    description = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        verbose_name = _("Config variables")
        verbose_name_plural = _("Config variables")

    def get_value(self) -> Union[str, date, datetime, None]:
        """
        Returns the variable value in the specified type.

        Returns:
            Union[str, date, datetime, None]: The value converted to the specified type.
                If conversion fails, returns None.
        """
        needed_type = ValueType(self.value_type).value or ValueType.TYPE_STR.value
        try:
            if self.value_type == ValueType.TYPE_DATE.value:
                return needed_type.strptime(self.value, "%Y-%m-%d").date()
            elif self.value_type == ValueType.TYPE_DATETIME.value:
                return needed_type.strptime(self.value, "%Y-%m-%d %H:%M:%S")
            else:
                return needed_type(self.value)
        except ValueError:
            return None


class EmailsWhiteList(BaseUuidModel):
    pattern_type = models.CharField(max_length=128, choices=WhiteListPatternType.choices)
    value = models.CharField(max_length=255)

    def __repr__(self):
        return f"EmailsWhiteList({self.pattern_type} : {self.value})"

    def __str__(self):
        return f"{self.pattern_type} : {self.value}"

    class Meta:
        verbose_name = "Emails White List"
        verbose_name_plural = "Emails White List"
        ordering = ("-created", "-updated")
