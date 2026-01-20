from .constants import *
from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.
from core.models import BaseUuidModel


class Settings(BaseUuidModel):

    name = models.CharField(max_length=128, unique=True)
    value = models.CharField(max_length=128)
    value_type = models.IntegerField(choices=SETTING_VALUE_TYPES, default=1)
    description = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        verbose_name = _('Config variables')
        verbose_name_plural = _('Config variables')

    def get_value(self):
        """ Returns variable value in specified type """
        needed_type = VALUES_TYPE_MAPPING.get(self.value_type, TYPE_STR)
        try:
            if self.value_type == TYPE_DATE:
                return  needed_type.strptime(self.value, '%Y-%m-%d').date()
            elif self.value_type == TYPE_DATETIME:
                return needed_type.strptime(self.value, '%Y-%m-%d %H:%M:%S')
            else:
                return needed_type(self.value)
        except:
            return None


class EmailsWhiteList(BaseUuidModel):
    pattern_type = models.CharField(max_length=128, choices=WHITE_LIST_PATTERN_TYPE_CHOICE)
    value = models.CharField(max_length=255)

    def __repr__(self):
        return f"EmailsWhiteList({self.pattern_type} : {self.value})"

    def __str__(self):
        return f"{self.pattern_type} : {self.value}"

    class Meta:
        verbose_name = "Emails White List"
        verbose_name_plural = "Emails White List"
        ordering = ('-created', '-updated')
