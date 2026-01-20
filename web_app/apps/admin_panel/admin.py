from django.contrib import admin

from apps.admin_panel.models import EmailsWhiteList, Settings
from apps.core.base_admin import BaseAdmin

@admin.register(Settings)
class SettingsAdmin(BaseAdmin):
    list_display = ("name", "value", "value_type")
    list_filter = ("value_type",)
    search_fields = ("name",)


@admin.register(EmailsWhiteList)
class EmailsWhiteListAdmin(BaseAdmin):
    list_display = ("value", "pattern_type", "created", "updated")
    list_filter = ("pattern_type", "created", "updated")
    search_fields = ("value",)
