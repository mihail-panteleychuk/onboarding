from django.contrib import admin

from .models import *

# Register your models here.

@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('name', 'value', 'value_type' )
    list_filter = ('value_type', )
    search_fields = ('name', )


