import re

from django.conf import settings
from django.db.models import Q
from django.db.models.functions import Now
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.payments.serializers import CardModelSerializer
from apps.subscription.constants import PaymentStatus
from apps.subscription.serializers import SubscriptionSerializer
from apps.user.models import Country, User
from apps.user.validators import validate_user_password


class CountrySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    name = serializers.CharField(required=False)

    class Meta:
        model = Country
        exclude = ("state",)


class PhoneCodeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = Country
        exclude = ("state", "country_code")


class CountryListSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    name = serializers.CharField(required=False)

    class Meta:
        model = Country
        fields = "__all__"


class ShortCountrySerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False)
    id = serializers.IntegerField()

    class Meta:
        model = Country
        fields = ("id", "name")


class ChangePasswordSerializer(serializers.ModelSerializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_user_password])

    class Meta:
        model = User
        fields = (
            "old_password",
            "new_password",
        )


class ChangeEmailSerializer(serializers.Serializer):
    password = serializers.CharField()
    new_email = serializers.EmailField()

    def validate(self, data):
        if not self.context["request"].user.check_password(data["password"]):
            raise serializers.ValidationError(
                {"detail": _("Current password is entered incorrectly")},
            )
        if self.context["request"].user.email == data["new_email"].lower():
            raise serializers.ValidationError(
                {"detail": _("You already have this email address. Kindly try another one!")},
            )
        if User.objects.filter(email=data["new_email"].lower()).count() > 0:
            # Already exists user with such email
            msg = (
                f'User with {data["new_email"]} already exists on the website. '
                f"Please try another email address or contact the user."
            )
            raise serializers.ValidationError({"detail": str(msg)})

        return data

    class Meta:
        fields = ("password", "new_email")


class LanguageSerializer(serializers.Serializer):
    name = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    class Meta:
        fields = ("name", "value")

    @staticmethod
    def get_name(obj):
        return obj[1]

    @staticmethod
    def get_value(obj):
        return obj[0]


class UserSocialAccountSerializer(serializers.ModelSerializer):
    facebook = serializers.CharField(required=False, source="facebook_user_id")
    apple = serializers.CharField(required=False, source="apple_user_id")
    google = serializers.CharField(required=False, source="google_user_id")

    class Meta:
        model = User
        fields = ("facebook", "apple", "google")


class FullUserInfoSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True)
    role = serializers.SerializerMethodField()
    accounts = serializers.SerializerMethodField()
    password_created = serializers.SerializerMethodField()
    email_added = serializers.SerializerMethodField()
    onboarding_finished = serializers.BooleanField(read_only=True)
    subscription = serializers.SerializerMethodField()
    card = serializers.SerializerMethodField()
    phone_code = PhoneCodeSerializer(allow_null=True)

    def get_card(self, obj):
        card = (
            obj.cards.filter(active=True)
            .select_related("card_billing", "card_billing__country")
            .first()
        )

        return CardModelSerializer(card, context=self.context).data if card else None

    def get_subscription(self, obj):
        subscription = (
            obj.subscriptions.filter(
                Q(expire_date__gt=Now()) | Q(next_payment_date__gt=Now()),
                start_date__lt=Now(),
                status__in=[
                    PaymentStatus.PAID,
                    PaymentStatus.PAID_CANCELED,
                    PaymentStatus.PENDING,
                    PaymentStatus.TRIAL,
                ],
            )
            .select_related("plan", "scheduled_plan")
            .first()
        )

        return (
            SubscriptionSerializer(subscription, context=self.context).data
            if subscription
            else None
        )

    @staticmethod
    def get_role(obj):
        return {"id": obj.role, "name": dict(User.UserRoleChoices.choices)[obj.role]}

    @staticmethod
    def get_password_created(obj):
        return not obj.check_password(settings.DEFAULT_PASSWORD)

    @staticmethod
    def get_email_added(obj):
        return not bool(re.match(r"\d+@temporary.com.uk$", obj.email))

    def get_accounts(self, obj):
        return UserSocialAccountSerializer(
            obj,
            context={"request": self.context.get("request")},
        ).data

    def update(self, instance, validated_data):
        if phone_code := validated_data.pop("phone_code", None):
            phone_code = Country.objects.get(**phone_code)
            setattr(instance, "phone_code", phone_code)
        return super().update(instance, validated_data)

    class Meta:
        model = User
        fields = (
            "id",
            "avatar",
            "email",
            "first_name",
            "last_name",
            "phone_code",
            "phone",
            "language",
            "role",
            "accounts",
            "subscription",
            "payment_service_user_id",
            "onboarding_finished",
            "email_added",
            "password_created",
            "card",
            "created",
        )
