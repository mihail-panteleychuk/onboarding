from rest_framework import serializers
from .models import Subscription, Plan


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ('id', 'name', 'monthly_price', 'amount_products_per_week', "status", "is_trial")


class ShortPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name']

class SubscriptionCreateViewSerializer(serializers.Serializer):
    discount_code = serializers.CharField(required=False)
    plan = serializers.IntegerField(required=True)
    payment = serializers.JSONField(required=False)

    # test if not passed: maybe need to set as required
    email_subscribed = serializers.BooleanField(default=True, source='send_news')

    class Meta:
        fields = ('discount_code', 'plan', 'payment', 'email_subscribed')

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer()
    payment_status = serializers.SerializerMethodField()
    active = serializers.SerializerMethodField()
    scheduled_plan = PlanSerializer(required=False, allow_null=True)

    class Meta:
        model = Subscription
        fields = ('id', 'plan', 'active', 'start_date', 'expire_date', 'payment_status', "next_payment_date", "scheduled_plan")

    def get_payment_status(self, obj):
        return obj.object_status

    def get_active(self, obj):
        return obj.active


