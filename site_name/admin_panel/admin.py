from django.contrib import admin

from .models import *

@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('name', 'value', 'value_type' )
    list_filter = ('value_type', )
    search_fields = ('name', )


@admin.register(EmailsWhiteList)
class EmailsWhiteListAdmin(admin.ModelAdmin):
    list_display = ('value', 'pattern_type', 'created', 'updated' )
    list_filter = ('pattern_type',  'created', 'updated')
    search_fields = ('value', )
