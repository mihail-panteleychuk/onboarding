from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.serializers import TokenObtainSerializer
from rest_framework_simplejwt.settings import api_settings

from apps.core.auth import CustomRefreshToken
from apps.user.models import User
from apps.user.serializers import FullUserInfoSerializer


class CustomTokenObtainPairSerializer(TokenObtainSerializer):
    default_error_messages = {
        "no_such_account": _("No account found with the given credentials"),
        "account_blocked": _("Your account is blocked. To unblock it please contact Support"),
        "no_active_account": _("No active account found with the given credentials"),
    }

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

        api_settings.USER_AUTHENTICATION_RULE(self.user)

        refresh = self.get_token(self.user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        data["user"] = FullUserInfoSerializer(self.user, context=self.context).data
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
            data["user"] = FullUserInfoSerializer(user, context=self.context).data

        return data


class SignUpSerializer(serializers.Serializer):
    """Сериализатор для регистрации нового пользователя"""
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)


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
                code="old_email_empty",
            )
        if not data["new_email"]:
            raise serializers.ValidationError(
                self.default_error_messages["new_email_empty"],
                code="new_email_empty",
            )
        if User.objects.filter(email=data["new_email"].lower()).exists():
            raise serializers.ValidationError(
                self.default_error_messages["new_email_exists"],
                code="new_email_exists",
            )
        self.instance = get_object_or_404(User.objects.all(), email=data["email"].lower())

        if self.instance.email_confirmed:
            raise serializers.ValidationError(
                self.default_error_messages["old_email_verified"],
                code="old_email_verified",
            )
        return {"email": data["new_email"]}

    def save(self, **kwargs):
        return super().save(**kwargs)

    class Meta:
        model = User
        fields = ("email", "new_email")
