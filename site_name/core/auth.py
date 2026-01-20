from django.apps import apps
from django.conf import settings
from django.contrib.postgres import aggregates
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import (AuthenticationFailed,
                                                 InvalidToken, TokenError)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.state import User
from rest_framework_simplejwt.token_blacklist.models import (BlacklistedToken,
                                                             OutstandingToken)
from rest_framework_simplejwt.tokens import AccessToken, Token, BlacklistMixin
from rest_framework_simplejwt.utils import datetime_from_epoch

__all__ = (
    'CustomBlacklistMixin', 'CustomJWTAuthentication', 'CustomRefreshToken', 'CustomAccessToken'
)


class CustomBlacklistMixin(BlacklistMixin):
    def check_blacklist(self):
        """
        Checks if this token is present in the token blacklist.  Raises
        `TokenError` if so.
        """
        jti = self.payload[api_settings.JTI_CLAIM]

        if BlacklistedToken.objects.filter(token__jti=jti).exists():
            raise TokenError(_('You have been logged out since you just signed into Account from another location.'))


class CustomJWTAuthentication(JWTAuthentication):
    EmailsWhiteList = apps.get_model('admin_panel.EmailsWhiteList')

    def authenticate(self, request):
        # ignore auth on sign-in/sign-up requests by social networks
        if request.get_full_path().startswith('/api/auth/social/'):
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
        Validates an encoded JSON web token and returns a validated token
        wrapper object.
        """
        messages = {}
        for AuthToken in api_settings.AUTH_TOKEN_CLASSES:
            try:
                return AuthToken(raw_token)
            except TokenError as e:
                messages = {'token_class': AuthToken.__name__,
                            'token_type': AuthToken.token_type,
                            'message': e.args[0]}

        raise InvalidToken({
            'detail': messages.get('message') or _("Given token not valid for any token type"),
            'messages': messages,
        })

    def check_user_email(self, user):
        # TODO  need a white_list?
        """
            Validating user email for test and stage environments.
            Grant access only for Emails from White List.
        """
        white_list_patterns = self.EmailsWhiteList.objects.all().values('pattern_type',).annotate(
            pattern=aggregates.ArrayAgg('value')
            ).values_list('pattern_type', 'pattern').order_by('pattern_type')

        email = user.email.strip()
        email_domain = email.split('@')[-1]

        for pattern_type, pattern in dict(white_list_patterns).items():
            if pattern_type == 'full' and email in pattern:
                break
            elif pattern_type == 'domain' and email_domain in pattern:
                break
        else:
            raise PermissionDenied(
                _('Your email is not permitted to authorize on the STAGE environment.'),
                code='permission_denied'
            )

    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken(_('Token contained no recognizable user identification'))

        try:
            user = User.objects.filter(**{api_settings.USER_ID_FIELD: user_id}).\
                only('pk', 'is_active', 'role').first()
                # select_related('company', 'company__country', 'user_billing', 'user_billing__country', 'user_billing__phone_code').first()
            if not user:
                raise User.DoesNotExist()

            if not settings.IS_PRODUCTION:
                self.check_user_email(user)
        except User.DoesNotExist:
            raise AuthenticationFailed(_('User not found'), code='user_not_found')

        if not user.is_active:
            raise AuthenticationFailed(_('User is inactive'), code='user_inactive')

        return user


class CustomRefreshToken(CustomBlacklistMixin, Token):

    token_type = 'refresh'
    lifetime = api_settings.REFRESH_TOKEN_LIFETIME
    no_copy_claims = (
        api_settings.TOKEN_TYPE_CLAIM,
        'exp',
        api_settings.JTI_CLAIM,
    )

    @classmethod
    def for_user(cls, user):
        """
        Adds this token to the outstanding token list.
        """
        blacklisted_tokens = []
        for token in list(OutstandingToken.objects.filter(user=user)):
            blacklisted_tokens.append(BlacklistedToken(token=token))
        BlacklistedToken.objects.bulk_create(
            blacklisted_tokens,
            batch_size=500,
            ignore_conflicts=True)

        token = super().for_user(user)

        jti = token[api_settings.JTI_CLAIM]
        exp = token['exp']

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
        Returns an access token created from this refresh token.  Copies all
        claims present in this refresh token to the new access token except
        those claims listed in the `no_copy_claims` attribute.
        """
        access = CustomAccessToken()

        # Use instantiation time of refresh token as relative timestamp for
        # access token "exp" claim.  This ensures that both a refresh and
        # access token expire relative to the same time if they are created as
        # a pair.
        access.set_exp(from_time=self.current_time)
        access['jti'] = self.payload['jti']
        no_copy = self.no_copy_claims
        for claim, value in self.payload.items():
            if claim in no_copy:
                continue
            access[claim] = value

        return access


class CustomAccessToken(AccessToken):

    def verify(self):
        super().verify()
        # check whether the token_jti has been blacklisted by new authorization
        if BlacklistedToken.objects.filter(token__jti=self.payload['jti']).exists():
            raise TokenError(_('You have been logged out since you just signed into Account from another location.'))
