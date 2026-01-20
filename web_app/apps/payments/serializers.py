from rest_framework import serializers

from apps.payments.models import BillingAddress, Card, Invoice, InvoiceLineItem
from apps.subscription.serializers import SubscriptionSerializer
from apps.user.models import Country


class CreateCardViewSerializer(serializers.Serializer):
    type = serializers.CharField(required=True)
    payment_method = serializers.JSONField(required=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    country = serializers.IntegerField(required=False)
    state = serializers.CharField(required=False, allow_null=True)

    class Meta:
        fields = ("payment_method", "first_name", "last_name", "country", "state", "type")


class StripeCardBillingSerializer(serializers.Serializer):
    address_line_1 = serializers.CharField(source="line1", required=False, allow_null=True)
    address_line_2 = serializers.CharField(source="line2", required=False, allow_null=True)
    city = serializers.CharField(required=False, allow_null=True)
    postal_code = serializers.CharField(required=False, allow_null=True)

    class Meta:
        fields = "__all__"


# =============================================================================


class CreateSubscriptionViewSerializer(CreateCardViewSerializer):
    plan = serializers.UUIDField(required=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    type = serializers.CharField(required=False)

    discount = serializers.CharField(required=False, allow_null=True, source="discount_code")
    payment_method = serializers.JSONField(required=False, allow_null=True)
    send_news = serializers.BooleanField(required=False)
    redirect_url = serializers.CharField(required=False, allow_null=True)

    class Meta:
        fields = (
            "payment_method",
            "first_name",
            "last_name",
            "country",
            "state",
            "type",
            "plan",
            "discount",
            "redirect_url",
        )


class UpdateSubscriptionViewSerializer(serializers.Serializer):
    plan = serializers.UUIDField(required=True, allow_null=True)
    force = serializers.BooleanField(default=False)
    discount = serializers.CharField(required=False, allow_null=True, source="discount_code")
    redirect_url = serializers.CharField(required=False, allow_null=True)

    class Meta:
        fields = ("plan", "discount", "force", "redirect_url")


class CountrySerializer2(serializers.ModelSerializer):
    id = serializers.IntegerField()
    name = serializers.CharField(required=False)

    class Meta:
        model = Country
        exclude = ("state",)


class BillingAddressModelSerializer(serializers.ModelSerializer):
    country = CountrySerializer2(allow_null=True, required=False)

    class Meta:
        model = BillingAddress
        exclude = ("created", "updated", "card")


class CardModelSerializer(serializers.ModelSerializer):
    country = CountrySerializer2(allow_null=True, required=False)
    card_billing = BillingAddressModelSerializer()

    class Meta:
        model = Card
        exclude = ("created", "updated", "payment_method_id", "user")


class ShortCardModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ("last4", "brand")


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    subscription = SubscriptionSerializer(allow_null=True)

    class Meta:
        model = InvoiceLineItem
        fields = ("subscription", "description", "price", "discount")


class ListInvoiceSerializer(serializers.ModelSerializer):
    card = ShortCardModelSerializer()
    status = serializers.JSONField(read_only=True, source="get_status_object")

    class Meta:
        model = Invoice
        fields = ("invoice_id", "status", "card", "issued", "total")


class DetailedInvoiceSerializer(serializers.ModelSerializer):
    card = CardModelSerializer()
    line_items = serializers.SerializerMethodField()
    status = serializers.JSONField(read_only=True, source="get_status_object")
    bill_from = serializers.SerializerMethodField()

    @staticmethod
    def get_bill_from():
        from .utils import retrieve_stripe_account_billing  # noqa: ABS101

        return retrieve_stripe_account_billing()

    @staticmethod
    def get_line_items(invoice):
        line_items = invoice.line_items.all().order_by("-price")
        return InvoiceLineItemSerializer(line_items, many=True).data

    class Meta:
        model = Invoice
        fields = (
            "invoice_id",
            "status",
            "bill_from",
            "line_items",
            "card",
            "issued",
            "credits_applied",
            "discount",
            "total",
        )
