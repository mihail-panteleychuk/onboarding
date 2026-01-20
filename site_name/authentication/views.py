from re import fullmatch

import jwt
import requests
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, generics, permissions
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenViewBase

from core.auth import CustomRefreshToken
from user.models import ConfirmCode, User
from user.serializers import FullUserInfoSerializer
from core.exceptions import CustomAPIException, APIException


from .serializers import (CustomTokenObtainPairSerializer, CustomTokenRefreshSerializer)
from django.db.models import Q
from django.utils.timezone import now
from .utils import *
from core.utils import send_confirm_email_message, send_restore_password_email


class BaseAuthView:

    def generate_auth_response(self, user):
        # generate default auth response with JWT tokens and user information
        refresh = CustomRefreshToken.for_user(user)  # generate token without username & password
        response = dict()
        response['refresh'] = str(refresh)
        response['access'] = str(refresh.access_token)
        response['user'] = FullUserInfoSerializer(user, context={'request': self.request}).data

        return Response(response)

    def validate_request_user(self,  user_with_social, social_data, social_type):
        """
        Try to find user by passed information from social network (facebook, apple, google)
        """
        error_disconnected = _("Your %(name)s Account is disconnected. To login enter your email and password.") % {
            'name': social_type
        }
        error_already_connected = _("This %{name}s Account is already connected to another account") % {
            'name': social_type
        }

        user = None

        if self.request.user.is_authenticated:  # check authenticated request

            if user_with_social and user_with_social != self.request.user:
                # try to connect social acc that is already connected to another site user
                raise CustomAPIException(
                    detail={"detail": error_already_connected},
                    code=HTTP_400_BAD_REQUEST
                )
            elif not user_with_social:
                # connect social media to existing user
                user = self.request.user
            elif user_with_social and user_with_social == self.request.user:
                # re authentication
                user = user_with_social

            else:
                pass

        else:  # check anonymous request
            temp_u = User.objects.filter(email=social_data.get('email', '').lower()).first()
            if user_with_social:
                if user_with_social.is_deleted:
                    # check if user is not blocked
                    raise CustomAPIException(
                        detail={'detail': "Your account is blocked. To unblock it please contact Support."},
                        code=HTTP_400_BAD_REQUEST
                    )
                elif not user_with_social.is_active:
                    # check if user is existing
                    raise CustomAPIException(
                        detail={'detail': "No active account found with the given credentials."},
                        code=HTTP_400_BAD_REQUEST
                    )
                user = user_with_social
            elif temp_u:
                # user is trying to sign in with social account after he already disconnect social account from profile
                if temp_u.is_deleted:
                    raise CustomAPIException(
                        detail={'detail': "Your account is blocked. To unblock it please contact Support."},
                        code=HTTP_400_BAD_REQUEST
                    )
                elif not temp_u.is_active:
                    raise CustomAPIException(
                        detail={'detail': "No active account found with the given credentials."},
                        code=HTTP_400_BAD_REQUEST
                    )
                raise CustomAPIException(
                    detail={'detail': error_disconnected},
                    code=HTTP_400_BAD_REQUEST
                )
        return user


class CustomTokenObtainPairView(TokenViewBase):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = (permissions.AllowAny, )

    def post(self, request, *args, **kwargs):
        try:
            return super(CustomTokenObtainPairView, self).post(request, *args, **kwargs)
        except CustomAPIException as e:
            raise e
        except APIException as e:
            raise CustomAPIException(
                detail=e.detail,
                code=e.status_code
            )
        except Exception as e:
            raise CustomAPIException(
                detail={'detail': str(e)},
                code=HTTP_400_BAD_REQUEST
            )
            # return Response(
            #     {"message": {"detail": _("The email or password you entered is incorrect.")}},
            #     status=HTTP_400_BAD_REQUEST
            # )


class CustomTokenRefreshView(TokenViewBase):
    serializer_class = CustomTokenRefreshSerializer


class AppleOAuth2:
    """apple authentication backend"""

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


class AppleTokenView(APIView, BaseAuthView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        access_token = request.data.get("access_token")
        appleAuth = AppleOAuth2()
        data = appleAuth.do_auth(access_token)

        user_by_social_id = User.objects.filter(Q(apple_user_id=data.get('email', ''))).first()
        validating_result = self.validate_request_user(user_by_social_id, data, 'Apple') or None

        # if validating_result and isinstance(validating_result, Response):
        #     return validating_result

        user = validating_result
        # user name provide from apple on first site connect
        first_name = self.request.data.get('user',{}).get('name',{}).get('firstName')
        last_name = self.request.data.get('user',{}).get('name',{}).get('lastName')

        if not user:
            user = User()
            user.email = data['email'].lower() if 'email' in data and data['email'] else generate_temp_email()
            user.apple_user_id = data.get('email')
            user.first_name = first_name
            user.last_name = last_name
            user.is_active = True
            user.password = make_password(settings.DEFAULT_PASSWORD)
            user.save()
        elif user.apple_user_id is None:
            user.apple_user_id = data['email']
            user.save()

        return self.generate_auth_response(user)


    def delete(self, request):
        if request.user.is_anonymous:
            return Response({"message": {"detail": _("Not Authenticated")}}, status=HTTP_401_UNAUTHORIZED)

        user = self.request.user
        if user.check_password(settings.DEFAULT_PASSWORD) and not user.facebook_user_id and not user.google_user_id:
            return Response({"message": {"detail": _("Action can not be complete. You do not have a password yet, therefore"
                "your account can be lost if you disconnect. Create a password, and you will "
                "be able to disconnect the social platform of your choice.")}}, status=HTTP_400_BAD_REQUEST)

        user.apple_user_id = None
        user.save()

        return Response(FullUserInfoSerializer(user, context={'request': self.request}).data, status=HTTP_200_OK)

class GoogleTokenView(APIView, BaseAuthView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        payload = {'access_token': request.data.get("access_token")}  # validate the token
        data = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', params=payload).json()
        if 'error' in data:
            raise exceptions.AuthenticationFailed(_('Something went wrong, kindly try again'))

        user_by_social_id = User.objects.filter(Q(google_user_id=data.get('email'))).first()
        validating_result = self.validate_request_user(user_by_social_id, data, 'Google') or None

        # if validating_result and isinstance(validating_result, Response):
        #     return validating_result

        user = validating_result
        if not user:
            user = User()
            user.email = data['email'] if 'email' in data and data['email'] else generate_temp_email()
            user.first_name = data.get('given_name')
            user.last_name = data.get('family_name')
            user.google_user_id = data.get('email')
            user.is_active = True
            user.password = make_password(settings.DEFAULT_PASSWORD)
            user.save()
        elif user.google_user_id is None:
            user.google_user_id = data.get('email')
            user.save()


        return self.generate_auth_response(user)

    def delete(self, request):
        if request.user.is_anonymous:
            return Response({"message": {"detail": _("Not Authenticated")}}, status=HTTP_401_UNAUTHORIZED)

        user = self.request.user
        if user.check_password(settings.DEFAULT_PASSWORD) and not user.facebook_user_id and not user.apple_user_id:
            return Response({"message": {"detail": _("Action can not be complete. You do not have a password yet, therefore"
                "your account can be lost if you disconnect. Create a password, and you will "
                "be able to disconnect the social platform of your choice.")}}, status=HTTP_400_BAD_REQUEST)

        user.google_user_id = None
        user.save()

        return Response(FullUserInfoSerializer(user, context={'request': self.request}).data, status=HTTP_200_OK)

class FacebookTokenView(APIView, BaseAuthView):
    permission_classes = [permissions.AllowAny]
    API_URL = "https://graph.facebook.com/v2.3/me"


    def post(self,request):
        params = {}
        params['access_token'] = request.data.get("access_token")
        params['fields'] = 'id,email,first_name,last_name'
        resp = requests.get(self.API_URL, params=params, headers={'Accept': "application/json"})
        if resp.status_code != 200:
            raise exceptions.AuthenticationFailed(_('Something went wrong, kindly try again'))
        data = resp.json()

        user_by_social_id = User.objects.filter(Q(facebook_user_id=data.get('email', data['id']))).first()
        validating_result = self.validate_request_user(user_by_social_id, data, 'Facebook') or None

        # if validating_result and isinstance(validating_result, Response):
        #     return validating_result

        user = validating_result
        if not user:
            user = User()
            user.facebook_user_id = data.get('email', data.get('id'))
            user.email = data.get('email', generate_temp_email()).lower()
            user.first_name = data.get('first_name')
            user.last_name = data.get('last_name')
            user.is_active = True
            user.password = make_password(settings.DEFAULT_PASSWORD)
            user.save()
        elif user.facebook_user_id is None:
            user.facebook_user_id = data.get('email', data['id'])
            user.save()

        return self.generate_auth_response(user)


    def delete(self, request):
        if request.user.is_anonymous:
            return Response({"message": {"detail": _("Not Authenticated")}}, status=HTTP_401_UNAUTHORIZED)

        user = self.request.user
        if user.check_password(settings.DEFAULT_PASSWORD) and not user.apple_user_id and not user.google_user_id:
            return Response({"message": {"detail": _("Action can not be complete. You do not have a password yet, therefore"
                "your account can be lost if you disconnect. Create a password, and you will "
                "be able to disconnect the social platform of your choice.")}}, status=HTTP_400_BAD_REQUEST)

        user.facebook_user_id = None
        user.save()

        return Response(FullUserInfoSerializer(user, context={'request': self.request}).data, status=HTTP_200_OK)

class ChangeUserEmail(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]


    def post(self, request, *args, **kwargs):
        data = request.data
        email = data.get('email')
        new_email = data.get('new_email')
        if not email:
            return Response({"message": {"detail": _("Old user email not providen.")}}, status=HTTP_400_BAD_REQUEST)
        if not new_email:
            return Response({"message": {"detail": _("New user email not providen.")}}, status=HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User.objects.all(), email=email.lower())

        if User.objects.filter(email=new_email.lower()).exists():
            return Response({"message": {"detail": _("This email already exists.")}}, status=HTTP_400_BAD_REQUEST)

        if user.is_active:
            return Response({"message": {"detail": _("User email is already verified.")}}, status=HTTP_400_BAD_REQUEST)

        user.email = new_email
        user.save()

        return Response({'status': 'success'}, status=HTTP_200_OK)


class SendConfirmationEmail(APIView, BaseAuthView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.query_params.get('code', '')
        if not all([code, code.isdigit()]):
            return Response({"message": {"detail": _('provide digital code')},
                             "status_code": 400}, status=HTTP_400_BAD_REQUEST)

        confirm_code = ConfirmCode.objects.filter(code=code, expiring_date__gt=now()).first()
        if not all([code, confirm_code]):
            return Response({"message": {"detail": _("Email not confirmed. Confirmation code is expired or does not exist.")},
                             "status_code": 400}, status=HTTP_400_BAD_REQUEST)

        if confirm_code.new_email is None:
            user = confirm_code.user
            user.is_active = True
            user.save()
            # confirm_code.delete()

        return self.generate_auth_response(user)


    def post(self, request):
        email = request.data.get('email')
        if not self.request.user.is_anonymous:
            if not fullmatch(r"[^@]+@[^@]+\.[^@]+", email) or not email:
                return Response({"message": {"detail": _("Please provide a valid email address")},
                            "status_code": 400}, status=HTTP_400_BAD_REQUEST)
            user = self.request.user

            last_name = user.last_name
            first_name = user.first_name
            user.email = email
            user.save()
            link = 'https://' + settings.FRONT_DOMAIN + '/success/{}'
            send_confirm_email_message(user, link, 'confirm_email.html')

        else:
            first_name = request.data.get('first_name')
            last_name = request.data.get('last_name')
            if not all([first_name, last_name, email]):
                return Response({"message": {"detail": _("Please provide first name, last name and email")},
                                "status_code": 400}, status=HTTP_400_BAD_REQUEST)

            if not fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
                return Response({"message": {"detail": _("Please provide a valid email address")},
                            "status_code": 400}, status=HTTP_400_BAD_REQUEST)

            user = User.objects.filter(email=email.lower()).first()
            if user and user.is_active:
                message = _("This email already exists.") if not any([user.facebook_user_id, user.google_user_id, user.apple_user_id]) else _("User with the given email already exists. Try to login with social networks.")
                return Response({"message": {"detail": message},
                                "status_code": 400}, status=HTTP_400_BAD_REQUEST)
            elif user:
                user.first_name = first_name
                user.last_name = last_name
            else:
                user = User(first_name=first_name,
                            last_name=last_name,
                            email=email, is_active=False)
            user.set_password(settings.DEFAULT_PASSWORD)
            user.save()

        return Response(_("Confirmation email was sent"))


class ForgotPasswordView(APIView, BaseAuthView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.query_params.get('code', 0)
        confirm_code = ConfirmCode.objects.filter(code=code, expiring_date__gt=now()).first()
        if not all([code, confirm_code]):
            raise CustomAPIException(detail={"detail": _("The code you entered is incorrect, please try again")}, code=HTTP_400_BAD_REQUEST)

        user = confirm_code.user
        user.save()
        confirm_code.delete()
        if self.request.user.is_authenticated and user == self.request.user:
            response = {"message": {"detail": _("Code is valid.")}}
        elif not self.request.user.is_authenticated:
            return self.generate_auth_response(user)
        elif user != self.request.user:
            return Response({"message": {"detail": _("The code you entered is incorrect, please try again")}}, status=HTTP_400_BAD_REQUEST)

        return Response(response, status=HTTP_200_OK)

    def post(self, request):
        email = request.data.get('email')

        if not email or not fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
            raise CustomAPIException(detail={"detail": _("Please provide a valid email address")}, code=HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email.lower()).first()
        if not user:
            raise CustomAPIException(detail={"detail": _("The email you entered is incorrect")}, code=HTTP_400_BAD_REQUEST)
        elif not user.is_active or user.is_deleted:
            raise CustomAPIException({"detail": _('Your account is blocked. To unblock it please contact Support')}, code=HTTP_400_BAD_REQUEST)
        send_restore_password_email(user, 'restore_password.html' )


        if self.request.user.is_authenticated:
            response = {"message": {"detail": _("Email with confirmation code was sent")}}
        else:
            response = _("Email with confirmation code was sent")

        return Response(response)
