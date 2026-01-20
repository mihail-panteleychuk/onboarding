from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_framework_simplejwt.serializers import (
    TokenObtainSerializer,
    login_rule,
    user_eligible_for_login,
)
from rest_framework_simplejwt.settings import api_settings

from site_name.core.auth import CustomRefreshToken
from site_name.user.models import User
from site_name.user.serializers import FullUserInfoSerializer


class CustomTokenObtainPairSerializer(TokenObtainSerializer):
    default_error_messages = {
        "no_such_account": _("No account found with the given credentials"),
        "account_blocked": _("Your account is blocked. To unblock it please contact Support"),
        "no_active_account": _("No active account found with the given credentials"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.user = None

    @classmethod
    def get_token(cls, user):
        return CustomRefreshToken.for_user(user)

    def validate(self, attrs):
        attrs[self.username_field] = (
            attrs[self.username_field].lower()
            if attrs[self.username_field]
            else attrs[self.username_field]
        )
        data = {}
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            "password": attrs["password"],
        }
        try:
            authenticate_kwargs["request"] = self.context["request"]
        except KeyError:
            pass

        self.user = authenticate(**authenticate_kwargs)

        getattr(login_rule, user_eligible_for_login)(self.user)

        refresh = self.get_token(self.user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        data["user"] = FullUserInfoSerializer(
            self.user,
            context={"request": self.context.get("request")},
        ).data
        return data


class CustomTokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    default_error_messages = {
        "invalid": _("Invalid data. Expected a dictionary, but got {datatype}."),
        "no_such_account": _("No account found with the given credentials"),
        "no_active_account": _("No active account found with the given credentials"),
        "account_blocked": _("Your account is blocked. To unblock it please contact Support"),
    }

    def validate(self, attrs):
        refresh = CustomRefreshToken(attrs["refresh"])
        user = User.objects.filter(id=refresh.access_token["user_id"]).first()

        if not user:
            raise exceptions.AuthenticationFailed(
                self.error_messages["no_such_account"],
                "no_such_account",
            )
        elif user.is_deleted:
            raise exceptions.AuthenticationFailed(
                self.error_messages["account_blocked"],
                "account_blocked",
            )
        elif not user.is_active:
            raise exceptions.AuthenticationFailed(
                self.error_messages["no_active_account"],
                "no_active_account",
            )

        data = {"access": str(refresh.access_token), "refresh": str(refresh)}
        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass
            refresh.set_jti()
            refresh.set_exp()
            data["refresh"] = str(refresh)
            data["access"] = str(refresh.access_token)
            data["user"] = FullUserInfoSerializer(
                user,
                context={"request": self.context.get("request")},
            ).data

        return data


class ChangeEmailSerializer(serializers.ModelSerializer):
    default_error_messages = {
        "old_email_empty": _("Old user email not providen."),
        "old_email_verified": _("User email is already verified."),
        "new_email_empty": _("New user email not providen."),
        "new_email_exists": _("This email already exists."),
    }

    email = serializers.EmailField()
    new_email = serializers.EmailField()

    def validate(self, data: dict[str, str]):
        if not data["email"]:
            raise serializers.ValidationError(
                self.default_error_messages["old_email_empty"],
                code=HTTP_400_BAD_REQUEST,
            )
        if not data["new_email"]:
            raise serializers.ValidationError(
                self.default_error_messages["new_email_empty"],
                code=HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(email=data["new_email"].lower()).exists():
            raise serializers.ValidationError(
                self.default_error_messages["new_email_exists"],
                code=HTTP_400_BAD_REQUEST,
            )
        self.instance = get_object_or_404(User.objects.all(), email=data["email"].lower())

        if self.instance.email_confirmed:
            raise serializers.ValidationError(
                self.default_error_messages["old_email_verified"],
                code=HTTP_400_BAD_REQUEST,
            )
        return {"email": data["new_email"]}

    def save(self, **kwargs):
        return super().save(**kwargs)

    class Meta:
        model = User
        fields = ("email", "new_email")
