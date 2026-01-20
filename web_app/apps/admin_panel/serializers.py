from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.user.validators import role_validator, validate_user_password


class BaseAdminPanelUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "avatar",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
            "is_deleted",
            "onboarding_finished",
            "password",
        )

    def create(self, validated_data):
        if "get_role_object" in validated_data:
            validated_data.update({"role": validated_data.pop("get_role_object")})

        if validated_data.get("password"):
            validated_data.update({"is_active": True, "email_subscribed": True})
        else:
            validated_data.update({"is_active": False, "email_subscribed": False})

        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "get_role_object" in validated_data:
            validated_data.update({"role": validated_data.pop("get_role_object")})
        return super().update(instance, validated_data)


class AdminPanelUserUpdateSerializer(BaseAdminPanelUserSerializer):
    role = serializers.JSONField(
        source="get_role_object",
        required=False,
        validators=[role_validator],
    )


class AdminPanelUserCreateSerializer(BaseAdminPanelUserSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_null=True,
        validators=[validate_user_password],
    )
    role = serializers.JSONField(
        source="get_role_object",
        default=get_user_model().UserRoleChoices.USER,
        validators=[role_validator],
    )

    def is_valid(self, raise_exception=False):
        if (
            get_user_model()
            .objects.filter(email__iexact=self.initial_data["email"].lower())
            .exists()
        ):
            msg = (
                f'User with {self.initial_data["email"]} already exists on the website. '
                "Please try another email address or contact the user."
            )
            raise serializers.ValidationError({"detail": msg})
        super().is_valid(raise_exception=raise_exception)
