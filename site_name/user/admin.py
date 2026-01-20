from django.contrib import admin
from rest_framework_simplejwt.tokens import OutstandingToken
from django.conf import settings
from .models import ( Country, User,)
# BillingAddress, CompanyDetails,

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'payment_service_user_id', 'role', 'is_active', 'is_staff', 'is_superuser', 'onboarding_finished', 'created', 'updated')
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'role')
    search_fields = ('email', 'first_name', 'last_name', 'payment_service_user_id')


    def save_model(self, request, obj, form, change):
        password = form.cleaned_data.get('password')
        super(UserAdmin, self).save_model(request, obj, form, change)
        password = password or settings.DEFAULT_PASSWORD
        if password and not password.startswith('pbkdf2_sha256$216000$') and len(password.split('$')) != 4 :
            obj.set_password(password)
            obj.save()

    def delete_user_without_warnings(self, request, queryset):
        users = queryset.values("id")
        OutstandingToken.objects.filter(user__id__in=users).delete()
        queryset.delete()

    actions = ("delete_user_without_warnings", )

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'flag', 'code', 'country_code')
    search_fields = ('name', 'code', 'country_code' )

# @admin.register(BillingAddress)
# class BillingAddressAdmin(admin.ModelAdmin):
#     list_display = [field.name for field in BillingAddress._meta.get_fields()]


# @admin.register(CompanyDetails)
# class CompanyDetailsAdmin(admin.ModelAdmin):
#     list_display = ('user', 'name', 'country', 'city', 'VAT')
#     search_fields = ('user__first_name', 'country__name', 'name', 'city', 'VAT')


