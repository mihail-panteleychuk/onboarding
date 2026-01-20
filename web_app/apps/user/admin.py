from django.conf import settings
from django.contrib import admin
from rest_framework_simplejwt.tokens import OutstandingToken

from apps.user.models import Country, User
from apps.core.base_admin import BaseAdmin


@admin.register(User)
class UserAdmin(BaseAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "payment_service_user_id",
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
        "onboarding_finished",
        "created",
        "updated",
    )
    list_filter = ("is_staff", "is_active", "is_superuser", "role")
    search_fields = ("email", "first_name", "last_name", "payment_service_user_id")

    def save_model(self, request, obj, form, change):
        password = form.cleaned_data.get("password")
        super().save_model(request, obj, form, change)
        password = password or settings.DEFAULT_PASSWORD
        if (
            password
            and not password.startswith("pbkdf2_sha256$216000$")
            and len(password.split("$")) != 4
        ):
            obj.set_password(password)
            obj.save()

    def delete_user_without_warnings(self, request, queryset):
        users = queryset.values("id")
        OutstandingToken.objects.filter(user__id__in=users).delete()
        queryset.delete()

    actions = ("delete_user_without_warnings",)


@admin.register(Country)
class CountryAdmin(BaseAdmin):
    list_display = ("name", "flag", "code", "country_code")
    search_fields = ("name", "code", "country_code")
