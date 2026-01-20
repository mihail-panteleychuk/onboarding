from datetime import timedelta
from random import randint
from re import fullmatch

import jwt
import requests
# from core.send_in_blue import *
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, permissions, exceptions
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenViewBase

from core.auth import CustomRefreshToken
from core.exceptions import CustomAPIException
from user.models import ConfirmCode, User
from user.serializers import AccountBillingSerializers
from .serializers import *
from .utils import generate_temp_email

__all__ = (
    'CustomTokenObtainPairView', 'CustomTokenRefreshView', 'AppleTokenView',
    'GoogleTokenView', 'FacebookTokenView', 'ChangeUserEmail',
    'SendConfirmationEmail', 'ForgotPasswordView',
)


class BaseSocialLoginView(APIView):

    def generate_response(self, user):
        # generate default auth response with JWT tokens and user information
        refresh = CustomRefreshToken.for_user(user)  # generate token without username & password
        response = dict()
        response['refresh'] = str(refresh)
        response['access'] = str(refresh.access_token)
        response['user'] = AccountBillingSerializers(user, context={'request': self.request}).data

        return response

    def get_user_by_social_info(self, social_id_field, social_data):
        """
        Try to find user by passed information from social network (facebook, apple, google)
        """
        # mapping for retrieving social information from social response
        social_id_mapping = {
            # social_id_field: lambda function
            'facebook_user_id': lambda: social_data.get('email') or social_data['id'],
            'apple_user_id': lambda: (social_data.get('email') or '').lower(),
            'google_user_id': lambda: (social_data.get('email') or '').lower()
        }
        filter_kwargs = {social_id_field: social_id_mapping[social_id_field]()}

        # mapping of social networks names
        names_mapping = {
            'facebook_user_id': 'Facebook',
            'apple_user_id': 'Apple',
            'google_user_id': 'Google'
        }

        error_disconnected = _("Your %(name)s Account is disconnected. To login enter your email and password.") % {
            'name': names_mapping[social_id_field]
        }
        error_already_connected = _("This %{name}s Account is already connected to another account") % {
            'name': names_mapping[social_id_field]
        }

        user_by_social_id = User.objects.filter(**filter_kwargs).first()  # find user by connected social account

        # check authenticated request
        if self.request.user.is_authenticated:
            if user_by_social_id and user_by_social_id != self.request.user:
                raise CustomAPIException(detail={"detail": error_already_connected},
                                         status=HTTP_400_BAD_REQUEST)
            elif not user_by_social_id:  # social account hasn't been connected yet
                return self.request.user
            elif user_by_social_id and user_by_social_id == self.request.user:
                # social account is already connected to request.user
                return user_by_social_id
            else:
                pass
        # check anonymous request
        else:
            # if we receive email from social network
            if social_data.get('email'):
                # try to find user with received email
                social_email = social_data.get('email').lower()
                temp_u = User.objects.filter(email=social_email).first()
                if user_by_social_id:
                    return user_by_social_id
                elif temp_u:
                    raise CustomAPIException(detail={"detail": error_disconnected},
                                             code=HTTP_400_BAD_REQUEST)
            return user_by_social_id


class CustomTokenObtainPairView(TokenViewBase):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        try:
            return super(CustomTokenObtainPairView, self).post(request, *args, **kwargs)
        except:
            raise CustomAPIException(detail={"detail": _("The email or password you entered is incorrect.")},
                                     code=HTTP_400_BAD_REQUEST)


class CustomTokenRefreshView(TokenViewBase):
    serializer_class = CustomTokenRefreshSerializer


class AppleOAuth2:
    """
    Apple authentication backend
    """

    name = 'apple'
    ACCESS_TOKEN_URL = 'https://appleid.apple.com/auth/token'
    SCOPE_SEPARATOR = ','
    ID_KEY = 'uid'

    def do_auth(self, access_token, *args, **kwargs):
        """
        Finish the auth process once the access_token was retrieved
        Get the email from ID token received from apple
        """
        response_data = {}
        id_token = access_token.encode('utf-8') if isinstance(access_token, str) else access_token
        if id_token:
            decoded = jwt.decode(id_token, "", options={"verify_signature": False}, algorithms=['RS256'])
            response_data.update({'email': decoded['email']}) if 'email' in decoded else None
            response_data.update({'uid': decoded['sub']}) if 'sub' in decoded else None

        response = kwargs.get('response') or {}
        response.update(response_data)
        response.update({'access_token': access_token}) if 'access_token' not in response else None

        return response


class AppleTokenView(BaseSocialLoginView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Sing-in/Sing-up with Apple account.
        Or connect Apple account to already existing Account.
        """
        access_token = request.data.get("access_token")
        appleAuth = AppleOAuth2()
        data = appleAuth.do_auth(access_token)

        user = self.get_user_by_social_info(social_id_field='apple_user_id', social_data=data)

        first_name = self.request.data.get('user', {}).get('name', {}).get('firstName')
        last_name = self.request.data.get('user', {}).get('name', {}).get('lastName')

        if not user:
            user = User()
            user.email = data['email'].lower() if 'email' in data and data['email'] else generate_temp_email()
            user.apple_user_id = data.get('email')
            user.first_name = first_name
            user.last_name = last_name
            user.email_confirmed = True
            user.password = make_password(settings.DEFAULT_PASSWORD)
            user.save()
        elif user.apple_user_id is None:
            user.apple_user_id = data['email']
            user.save()
        response = self.generate_response(user)

        return Response(response)

    def delete(self, request):
        if request.user.is_anonymous:
            return Response({"message": {"detail": _("Not Authenticated")}}, status=HTTP_400_BAD_REQUEST)

        user = self.request.user
        if user.check_password(settings.DEFAULT_PASSWORD) and not user.facebook_user_id and not user.google_user_id:
            return Response({"message": {"detail": _(
                "Action can not be complete. You do not have a password yet, therefore"
                "your account can be lost if you disconnect. Create a password, and you will "
                "be able to disconnect the social platform of your choice."
            )}}, status=HTTP_400_BAD_REQUEST)

        user.apple_user_id = None
        user.save()

        return Response(AccountBillingSerializers(user, context={'request': self.request}).data, status=HTTP_200_OK)


class GoogleTokenView(BaseSocialLoginView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        Sing-in/Sing-up with Google account.
        Or connect Google account to already existing Account.
        """
        payload = {'access_token': request.data.get("access_token")}  # validate the token
        data = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', params=payload).json()
        if 'error' in data:
            raise exceptions.AuthenticationFailed(_('Something went wrong, kindly try again'))

        user = self.get_user_by_social_info(social_id_field='google_user_id', social_data=data)

        if not user:
            user = User()
            user.email = data['email'] if 'email' in data and data['email'] else generate_temp_email()
            user.first_name = data.get('given_name')
            user.last_name = data.get('family_name')
            user.google_user_id = data.get('email')
            user.email_confirmed = True
            user.password = make_password(settings.DEFAULT_PASSWORD)
            user.save()
        elif user.google_user_id is None:
            user.google_user_id = data.get('email')
            user.save()

        response = self.generate_response(user)

        return Response(response)

    def delete(self, request):
        """
        Disconnect social account from Account
        """
        if request.user.is_anonymous:
            return Response({"message": {"detail": _("Not Authenticated")}}, status=HTTP_400_BAD_REQUEST)

        user = self.request.user
        if user.check_password(settings.DEFAULT_PASSWORD) and not user.facebook_user_id and not user.apple_user_id:
            return Response({"message": {"detail": _(
                "Action can not be complete. You do not have a password yet, therefore"
                "your account can be lost if you disconnect. Create a password, and you will "
                "be able to disconnect the social platform of your choice."
            )}}, status=HTTP_400_BAD_REQUEST)

        user.google_user_id = None
        user.save()

        return Response(AccountBillingSerializers(user, context={'request': self.request}).data, status=HTTP_200_OK)


class FacebookTokenView(BaseSocialLoginView):
    permission_classes = [permissions.AllowAny]
    API_URL = "https://graph.facebook.com/v2.3/me"

    def post(self, request):
        """
        Sing-in/Sing-up with Facebook account.
        Or connect Facebook account to already existing Account.
        """
        params = {}
        params['access_token'] = request.data.get("access_token")
        params['fields'] = 'id,email,first_name,last_name'
        resp = requests.get(self.API_URL, params=params, headers={'Accept': "application/json"})
        if resp.status_code != 200:
            raise exceptions.AuthenticationFailed(_('Something went wrong, kindly try again'))
        data = resp.json()

        user = self.get_user_by_social_info(social_id_field='facebook_user_id', social_data=data)
        if not user:
            user = User()
            user.facebook_user_id = data.get('email', data.get('id'))
            user.email = data.get('email', generate_temp_email()).lower()
            user.first_name = data.get('first_name')
            user.last_name = data.get('last_name')
            user.email_confirmed = True
            user.password = make_password(settings.DEFAULT_PASSWORD)
            user.save()
        elif user.facebook_user_id is None:
            user.facebook_user_id = data.get('email', data['id'])
            user.save()

        response = self.generate_response(user)

        return Response(response)

    def delete(self, request):
        """
        Disconnect social account from Account
        """
        if request.user.is_anonymous:
            return Response({"message": {"detail": _("Not Authenticated")}}, status=HTTP_400_BAD_REQUEST)

        user = self.request.user
        if user.check_password(settings.DEFAULT_PASSWORD) and not user.apple_user_id and not user.google_user_id:
            return Response({"message": {"detail": _(
                "Action can not be complete. You do not have a password yet, therefore"
                "your account can be lost if you disconnect. Create a password, and you will "
                "be able to disconnect the social platform of your choice."
            )}}, status=HTTP_400_BAD_REQUEST)

        user.facebook_user_id = None
        user.save()

        return Response(AccountBillingSerializers(user, context={'request': self.request}).data, status=HTTP_200_OK)


class ChangeUserEmail(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data
        email = data.get('email')
        new_email = data.get('new_email')
        if not email:
            return Response({"message": {"detail": _("Old user email not provided.")}}, status=HTTP_400_BAD_REQUEST)
        if not new_email:
            return Response({"message": {"detail": _("New user email not provided.")}}, status=HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User.objects.all(), email=email.lower())

        if User.objects.filter(email=new_email.lower()).exists():
            return Response({"message": {"detail": _("This email already exists.")}}, status=HTTP_400_BAD_REQUEST)

        if user.email_confirmed:
            return Response({"message": {"detail": _("User email is already verified.")}}, status=HTTP_400_BAD_REQUEST)

        user.email = new_email
        user.save()

        return Response({'status': 'success'}, status=HTTP_200_OK)


class SendConfirmationEmail(BaseSocialLoginView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.query_params.get('code')
        if not all([code, code.isdigit()]):
            return Response({"message": {"detail": _('provide digital code')},
                             "status_code": 400}, status=HTTP_400_BAD_REQUEST)

        confirm_code = ConfirmCode.objects.filter(code=code, expiring_date__gt=now()).first()
        if not all([code, confirm_code]):
            return Response(
                {"message": {"detail": _("Email not confirmed. Confirmation code is expired or does not exist.")},
                 "status_code": 400}, status=HTTP_400_BAD_REQUEST
            )

        if confirm_code.new_email is None:
            user = confirm_code.user
            user_was_already_activated = bool(user.is_active)
            user.is_active = True
            user.email_confirmed = True
            user.save()
            # if not user_was_already_activated:
            #     target_list = [settings.SIB_EMAIL_CONFIRMED_GROUP]
            #     sync_with_send_in_blue(user, target_list)

        response = self.generate_response(user)

        return Response(response)

    def post(self, request):
        email = request.data.get('email')
        if not self.request.user.is_anonymous:
            if not fullmatch(r"[^@]+@[^@]+\.[^@]+", email) or not email:
                return Response(
                    {"message": {"detail": _("Please provide a valid email address")},
                     "status_code": 400}, status=HTTP_400_BAD_REQUEST
                )
            user = self.request.user
            last_name = user.last_name
            first_name = user.first_name
            user.email = email
            user.save()
            link = f'https://{settings.API_DOMAIN}/api/success/'

        else:
            first_name = request.data.get('first_name')
            last_name = request.data.get('last_name')
            if not all([first_name, last_name, email]):
                return Response({"message": {"detail": _("Please provide first name, last name and email")},
                                "status_code": 400}, status=HTTP_400_BAD_REQUEST)

            if not fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
                return Response(
                    {"message": {"detail": _("Please provide a valid email address")},
                     "status_code": 400}, status=HTTP_400_BAD_REQUEST
                )

            user = User.objects.filter(email=email.lower()).first()
            if user and user.is_active:
                message = _("This email already exists.") if not any([user.facebook_user_id, user.google_user_id, user.apple_user_id]) else _("User with the given email already exists. Try to login with social networks.")
                return Response(
                    {"message": {"detail": message},
                     "status_code": 400}, status=HTTP_400_BAD_REQUEST
                )
            elif user:
                user.first_name = first_name
                user.last_name = last_name
            else:
                user = User(first_name=first_name, last_name=last_name, email=email, is_active=False)
            user.set_password(settings.DEFAULT_PASSWORD)
            user.save()
            link = f'https://{settings.API_DOMAIN}/api/sign-up/confirm/'

        confirm_code = ConfirmCode.objects.filter(user=user).first()

        if not confirm_code:
            confirm_code = ConfirmCode(user=user)
        confirm_code.code = randint(1111111111, 9999999999)
        confirm_code.expiring_date = now() + timedelta(hours=24)
        confirm_code.save()

        link = link + str(confirm_code.code)
        subj = _('Verify your account')
        message = 'confirm_email.txt'
        message = render_to_string(message, {'link': link})
        html_message = 'confirm_email.html'
        html_message = render_to_string(html_message, {'link': link})
        _from = f'"DataForest" <{settings.EMAIL_HOST_USER}>'
        try:
            result = send_mail(
                subject=str(subj),
                message=message,
                html_message=html_message,
                from_email=_from,
                recipient_list=[email, ],
                auth_user=settings.EMAIL_HOST_USER,
                auth_password=settings.EMAIL_HOST_PASSWORD
            )
        except:
            result = 0

        if result:
            return Response(_("Confirmation email was sent"), status=HTTP_200_OK)
        else:
            return Response(_("Confirmation email was not sent"), status=HTTP_400_BAD_REQUEST)


class ForgotPasswordView(BaseSocialLoginView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.query_params.get('code')
        confirm_code = ConfirmCode.objects.filter(code=code, expiring_date__gt=now()).first()
        if not all([code, confirm_code]):
            return Response(
                {"message": {"detail": _("The code you entered is incorrect, please try again")},
                 "status_code": 400}, status=HTTP_400_BAD_REQUEST)

        user = confirm_code.user
        user.is_active = True
        user.save()
        confirm_code.delete()
        if self.request.user.is_authenticated and user == self.request.user:
            response = {"message": {"detail": _("Code is valid.")}}
        elif not self.request.user.is_authenticated:
            response = self.generate_response(user)
        elif user != self.request.user:
            return Response(
                {"message": {"detail": _("The code you entered is incorrect, please try again")}},
                status=HTTP_400_BAD_REQUEST
            )

        return Response(response, status=HTTP_200_OK)

    def post(self, request):
        email = request.data.get('email')

        if not email or not fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
            return Response({"message": {"detail": _("Please provide a valid email address")},
                             "status_code": 400}, status=HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email.lower()).first()
        if not user:
            return Response({"message": {"detail": _("The email you entered is incorrect")},
                             "status_code": 400}, status=HTTP_400_BAD_REQUEST)

        confirm_code = ConfirmCode.objects.filter(user=user).first()
        if not confirm_code:
            confirm_code = ConfirmCode(user=user)
        confirm_code.code = randint(111111, 999999)
        confirm_code.expiring_date = now() + timedelta(hours=24)
        confirm_code.save()

        message = 'restore_password.txt'
        message = render_to_string(message, {'code': confirm_code.code})
        html_message = 'restore_password.html'
        html_message = render_to_string(html_message, {'code': confirm_code.code})
        subj = _('Reset your password')
        _from = f'"DataForest" <{settings.EMAIL_HOST_USER}>'
        try:
            result = send_mail(
                subject=str(subj),
                message=message,
                html_message=html_message,
                from_email=_from,
                recipient_list=[user.email, ],
                auth_user=settings.EMAIL_HOST_USER,
                auth_password=settings.EMAIL_HOST_PASSWORD
            )
        except:
            result = 0

        if result:
            if self.request.user.is_authenticated:
                # response for User on Settings page
                response = {"message": {"detail": _("Email with confirmation code was sent")}}
            else:
                # response for User on onboarding page
                response = _("Email with confirmation code was sent")
            return Response(response)
        else:
            return Response(
                {"message": {"detail": _("Email with confirmation code was not sent")}},
                status=HTTP_400_BAD_REQUEST)
