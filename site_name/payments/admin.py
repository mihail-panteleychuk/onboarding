from django.contrib import admin
from .models import *
# Register your models here.



@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("user", "card_holder_first_name", "card_holder_last_name", "last_4", "billing", "active")
    list_filter = ("active",)
    search_fields = ("user__first_name", "user__last_name", "card_holder_first_name", "card_holder_last_name")


@admin.register(CardBillingInfo)
class CardBillingInfoAdmin(admin.ModelAdmin):
    list_display = ("country", "postal_code", "city", "state", "address_1", "card")
    search_fields = ("country__name", "card__card_holder_first_name", "card__card_holder_last_name")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_id", "user", "card", "status", "total", "issued_date")
    list_filter = ("status", "issued_date")
    filter_horizontal = ('subscription', )
    search_fields = ("user__first_name", "user__last_name", "user__email", "card__last_4",
                     "card__card_holder_first_name", "card__card_holder_last_name")



@admin.register(SubscriptionType)
class SubscriptionTypeAdmin(admin.ModelAdmin):
    list_display = ("subscription", "get_email", "get_user", "get_plan", "get_category", "price", 'get_invoices')
    list_filter = ("subscription__plan", "subscription__category")

    search_fields = ("subscription__user__email", )

    def get_invoices(self,obj):
        return str(list(obj.invoices.all().values_list('invoice_id', flat=True)))

    def get_user(self, obj):
        return obj.subscription.user.email

    def get_plan(self, obj):
        return str(obj.subscription.plan)

    def get_category(self, obj):
        return str(obj.subscription.category)
    get_category.admin_order_field  = 'subscription'

    def get_email(self, obj):

        return obj.subscription.user.email
    get_email.admin_order_field  = 'subscription.user'

@admin.register(BillFromAddress)
class BillFromAddressAdmin(admin.ModelAdmin):
    list_display = ("country", "city", "state", "name", "address_line_1", "address_line_2", "postal_code", "VAT")
    list_filter = ("active", )

    search_fields = ("name", "country__name", "city")
