from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.postgres import aggregates
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, BlacklistMixin, Token
from rest_framework_simplejwt.utils import datetime_from_epoch

User = get_user_model()


default_error_messages = {
    "no_such_account": _("No account found with the given credentials"),
    "account_blocked": _("Your account is blocked. To unblock it please contact Support."),
    "no_active_account": _("No active account found with the given credentials."),
}


def user_authentication_rule(user):
    if not user:
        raise AuthenticationFailed(detail={"detail": default_error_messages["no_such_account"]})
    elif user.is_deleted:
        raise AuthenticationFailed(detail={"detail": default_error_messages["account_blocked"]})
    elif not user.is_active:
        raise AuthenticationFailed(detail={"detail": default_error_messages["no_active_account"]})
    return True


class CustomModelAuthBackend(ModelBackend):
    """
    Custom authentication backend for Django models, extending the ModelBackend to enforce authentication rules
       based on user activity and deletion status
    """

    def user_can_authenticate(self, user):
        """
        Check if the user can authenticate.

        Reject users with is_active=False. Custom user models that don't have that attribute are allowed.

        Args:
            user (User): The user object to check.

        Raises:
            AuthenticationFailed: If the user is not active or has been deleted.

        Returns:
            bool: True if the user can authenticate, False otherwise.
        """
        if not user:
            raise AuthenticationFailed(
                detail={"detail": default_error_messages["no_such_account"]},
            )
        elif user.is_deleted:
            raise AuthenticationFailed(
                detail={"detail": default_error_messages["account_blocked"]},
            )
        elif not user.is_active:
            raise AuthenticationFailed(
                detail={"detail": default_error_messages["no_active_account"]},
            )

        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None


class CustomBlacklistMixin(BlacklistMixin):
    """
    Custom mixin for handling token blacklisting.

    Adds custom logic to check if a token is present in the token blacklist
    """

    def check_blacklist(self):
        """
        Check if the token is present in the token blacklist.

        Raises:
            TokenError: If the token is blacklisted.

        """
        jti = self.payload[api_settings.JTI_CLAIM]

        if BlacklistedToken.objects.filter(token__jti=jti).exists():
            raise TokenError(
                _(
                    "You have been logged out since you just "
                    "signed into InHouse from another location.",
                ),
            )


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication class
    """

    EmailsWhiteList = apps.get_model("admin_panel.EmailsWhiteList")

    def authenticate(self, request):
        """
        Authenticate the user using JWT token.

        Args:
            request: The HTTP request object.

        Returns:
            tuple: A tuple containing the authenticated user and the validated token.

        """
        # ignore auth on sign-in/sign-up requests by social networks
        if request.get_full_path().startswith("/api/auth/social/"):
            return None

        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

    def get_validated_token(self, raw_token):
        """
        Validate an encoded JSON web token and return a validated token wrapper object.

        Args:
            raw_token (str): The raw encoded token.

        Returns:
            Token: The validated token object.

        Raises:
            InvalidToken: If the token is not valid.

        """
        messages = {}
        for auth_token in api_settings.AUTH_TOKEN_CLASSES:
            try:
                return auth_token(raw_token)
            except TokenError as e:
                messages = {
                    "token_class": auth_token.__name__,
                    "token_type": auth_token.token_type,
                    "message": e.args[0],
                }

        raise InvalidToken(
            {
                "detail": messages.get("message") or _("Given token not valid for any token type"),
                "messages": messages,
            },
        )

    def check_user_email(self, user):
        """
        Validate the user email for test and stage environments.

        Grant access only for `dropship.io` and `dataforest.ai` domains.

        Args:
            user (User): The user object.

        Raises:
            PermissionDenied: If the user's email is not permitted to authorize on the stage environment.

        """
        white_list_patterns = (
            self.EmailsWhiteList.objects.all()
            .values(
                "pattern_type",
            )
            .annotate(
                pattern=aggregates.ArrayAgg("value"),
            )
            .values_list(
                "pattern_type",
                "pattern",
            )
            .order_by("pattern_type")
        )

        email = user.email.strip()
        email_domain = email.split("@")[-1]

        for pattern_type, pattern in dict(white_list_patterns).items():
            if pattern_type == "full" and email in pattern:
                break
            elif pattern_type == "domain" and email_domain in pattern:
                break
        else:
            raise PermissionDenied(
                _("Your email is not permitted to authorize on the STAGE environment."),
                code="permission_denied",
            )

    def get_user(self, validated_token):
        """
        Attempt to find and return a user using the given validated token.

        Args:
            validated_token (Token): The validated token object.

        Returns:
            User: The authenticated user object.

        Raises:
            AuthenticationFailed: If the user is not found or is inactive.

        """
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken(_("Token contained no recognizable user identification"))

        try:
            user = (
                User.objects.filter(**{api_settings.USER_ID_FIELD: user_id})
                .only("pk", "is_active", "role")
                .first()
            )
            if not user:
                raise User.DoesNotExist()

            if not settings.IS_PRODUCTION:
                self.check_user_email(user)
        except User.DoesNotExist:
            raise AuthenticationFailed(_("User not found"), code="user_not_found")

        if not user.is_active:
            raise AuthenticationFailed(_("User is inactive"), code="user_inactive")

        return user


class CustomRefreshToken(CustomBlacklistMixin, Token):
    """
    Custom refresh token class that extends the Token class and includes
    additional functionality for blacklisting and outstanding tokens.
    """

    token_type = "refresh"
    lifetime = api_settings.REFRESH_TOKEN_LIFETIME
    no_copy_claims = (
        api_settings.TOKEN_TYPE_CLAIM,
        "exp",
        api_settings.JTI_CLAIM,
    )

    @classmethod
    def for_user(cls, user):
        """
        Adds this token to the outstanding token list and blacklists existing tokens.

        Args:
            user (User): The user for whom the token is being created.

        Returns:
            CustomRefreshToken: The created refresh token.
        """
        blacklisted_tokens = [
            BlacklistedToken(token=token) for token in OutstandingToken.objects.filter(user=user)
        ]
        BlacklistedToken.objects.bulk_create(
            blacklisted_tokens,
            batch_size=500,
            ignore_conflicts=True,
        )
        token = super().for_user(user)
        jti = token[api_settings.JTI_CLAIM]
        exp = token["exp"]
        OutstandingToken.objects.get_or_create(
            user=user,
            jti=jti,
            token=str(token),
            created_at=token.current_time,
            expires_at=datetime_from_epoch(exp),
        )
        return token

    @property
    def access_token(self):
        """
        Creates and returns an access token from this refresh token, copying
            all claims except those listed in `no_copy_claims`.

        Returns:
            CustomAccessToken: The created access token.
        """
        access = CustomAccessToken()

        # Use instantiation time of refresh token as relative timestamp for
        # access token "exp" claim.  This ensures that both a refresh and
        # access token expire relative to the same time if they are created as
        # a pair.
        access.set_exp(from_time=self.current_time)
        access["jti"] = self.payload["jti"]
        no_copy = self.no_copy_claims
        for claim, value in self.payload.items():
            if claim in no_copy:
                continue
            access[claim] = value
        return access


class CustomAccessToken(AccessToken):
    """
    Custom access token class that extends the AccessToken class and includes
    additional verification to check for blacklisted tokens.
    """

    def verify(self):
        """
        Verifies the access token. Checks if the token's JTI (JWT ID) has been
            blacklisted. Raises a TokenError if the token has been blacklisted.

        Raises:
            TokenError: If the token's JTI is found in the blacklist.
        """
        super().verify()
        jti = self.payload["jti"]
        # check whether the token_jti has been blacklisted by new authorization
        if jti and BlacklistedToken.objects.filter(token__jti=jti).exists():
            raise TokenError(
                _(
                    "You have been logged out since you just "
                    "signed into InHouse from another location.",
                ),
            )
