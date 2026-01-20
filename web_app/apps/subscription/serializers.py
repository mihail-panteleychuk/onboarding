from rest_framework import serializers

from apps.subscription.models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "id",
            "name",
            "description",
            "monthly_price",
            "amount_products_per_week",
            "status",
            "is_trial",
        )


class ShortPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "name", "monthly_price", "amount_products_per_week"]


class SubscriptionCreateViewSerializer(serializers.Serializer):
    discount_code = serializers.CharField(required=False)
    plan = serializers.CharField(required=True)
    payment = serializers.JSONField(required=False)
    billing_address = serializers.JSONField(required=False)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)

    phone = serializers.CharField(required=False, allow_null=True)
    phone_code = serializers.CharField(required=False, source="country_code", allow_null=True)
    # test if not passed: maybe need to set as required
    email_subscribed = serializers.BooleanField(default=True, source="send_news")

    class Meta:
        fields = (
            "discount_code",
            "plan",
            "payment",
            "email_subscribed",
            "billing_address",
            "first_name",
            "last_name",
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = ShortPlanSerializer()
    payment_status = serializers.SerializerMethodField()
    active = serializers.SerializerMethodField()
    scheduled_plan = ShortPlanSerializer(required=False, allow_null=True)

    class Meta:
        model = Subscription
        fields = (
            "id",
            "plan",
            "scheduled_plan",
            "active",
            "start_date",
            "payment_status",
            "next_payment_date",
            "expire_date",
        )

    @staticmethod
    def get_payment_status(obj):
        return obj.object_status

    @staticmethod
    def get_active(obj):
        return obj.active
