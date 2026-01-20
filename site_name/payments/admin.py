from django.contrib import admin
from .models import *
# Register your models here.



@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("user", "brand", "country",  "last4", "exp_month", "exp_year", "active", "payment_method_id")
    list_filter = ("active",)
    search_fields = ("user__first_name", "user__last_name", "user__email","last4", "brand")


@admin.register(BillingAddress)
class CardBillingDetailsAdmin(admin.ModelAdmin):
    list_display = ("card", "first_name", "last_name", "city", "country", "address_line_1", "postal_code")
    search_fields = ("first_name", "last_name", "country__name", "postal_code",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_id", "user", "card", "status", "total", "issued_date", "credits_applied", "discount")
    list_filter = ("status", "issued_date")
    # filter_horizontal = ('line_item', )
    search_fields = ("user__first_name", "user__last_name", "user__email", "card__last4",)


@admin.register(InvoiceLineItem)
class InvoiceLineItemAdmin(admin.ModelAdmin):
    list_display = ("subscription", 'get_user', "invoice", "price", "discount", "get_plan", )
    list_filter = ("subscription__plan", 'subscription__status')

    search_fields = ("subscription__user__email", )

    def get_user(self, obj):
        try:
            return obj.subscription.user.email
        except:
            return None

    get_user.admin_order_field  = 'subscription.user'

    def get_plan(self, obj):
        try:
            return str(obj.subscription.plan)
        except:
            return None

