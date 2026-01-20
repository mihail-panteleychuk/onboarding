from django.contrib import admin
from rest_framework_simplejwt.tokens import OutstandingToken
from django.conf import settings
from .models import User


# BillingAddress, CompanyDetails,

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'is_superuser', 'created', 'updated')
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'role')
    search_fields = ('email', 'first_name', 'last_name')

    def save_model(self, request, obj, form, change):
        password = form.cleaned_data.get('password')
        super(UserAdmin, self).save_model(request, obj, form, change)
        password = password or settings.DEFAULT_PASSWORD
        if password and not password.startswith('pbkdf2_sha256$216000$') and len(password.split('$')) != 4:
            obj.set_password(password)
            obj.save()

    def delete_user_without_warnings(self, request, queryset):
        users = queryset.values("id")
        OutstandingToken.objects.filter(user__id__in=users).delete()
        queryset.delete()

    actions = ("delete_user_without_warnings",)
