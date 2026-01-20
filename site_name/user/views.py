from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from random import randint
from smtplib import SMTP

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as rest_filter
from rest_framework import permissions, status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .filters import UserFilter
from .models import ConfirmCode, User
from .serializers import (ChangeEmailSerializer, ChangePasswordSerializer,
                          FullUserInfoSerializer)


class UserViewSet(viewsets.GenericViewSet, mixins.UpdateModelMixin):
    queryset = User.objects.all()
    serializer_class = FullUserInfoSerializer
    filter_backends = (rest_filter.DjangoFilterBackend, OrderingFilter)
    filterset_class = UserFilter
    ordering_fields = ('first_name', 'last_name', 'email', 'created')
    permission_classes = (IsAuthenticated,)
    lookup_field = None
    lookup_url_kwarg = None

    def get_object(self):
        if self.request.user.is_anonymous:
            return super(UserViewSet, self).get_object()
        else:
            return self.request.user

    @action(detail=False, methods=['GET'], url_path='account',
            permission_classes=[permissions.IsAuthenticated],
            serializer_class=FullUserInfoSerializer)
    def account(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['PUT', 'PATCH'], url_path='update',
            permission_classes=[permissions.IsAuthenticated],
            serializer_class=FullUserInfoSerializer)
    def update_user(self, request):
        """ Update all user info """
        if request.method == 'PATCH':
            return super(UserViewSet, self).partial_update(request)
        else:
            return super(UserViewSet, self).update(request)

    @action(detail=False, methods=['PUT'], permission_classes=[permissions.IsAuthenticated],
            serializer_class=ChangePasswordSerializer)
    def change_password(self, request):
        """ Update user password """
        user = self.request.user
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            if not user.check_password(request.data.get("old_password")):
                response = {
                    "message": {"detail": _("Current password is entered incorrectly"), 'type': "current_password"}}

                return Response(response, status=status.HTTP_400_BAD_REQUEST)
            if user.check_password(request.data.get("new_password")):
                response = {"message": {"detail": _("You already have this password"), 'type': "new_password"}}

                return Response(response, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(request.data.get("new_password"))
            user.save()

            return Response({"message": {"detail": _("Your password has successfully changed!"), 'type': "success"}},
                            status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], permission_classes=[permissions.IsAuthenticated],
            serializer_class=ChangePasswordSerializer)
    def set_password(self, request):
        """ Set user new password """
        user = self.request.user

        if not user.is_active:
            return Response(
                {"message": {"detail": _("User email is not confirmed.")},
                 "status_code": 400}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data.copy()
        data['old_password'] = settings.DEFAULT_PASSWORD
        serializer = ChangePasswordSerializer(data=data)



        if serializer.is_valid():
            # Check old password
            if user.check_password(data.get("new_password")):
                response = {
                    "password": [_('You already have this password')]
                }
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

            # set_password also hashes the password that the user will get
            user.set_password(data.get("new_password"))
            user.is_active = True
            user.save()
            code = ConfirmCode.objects.filter(user=user, expiring_date__gt=now(), new_email__isnull=True,
                                              new_password__isnull=True).first()
            if code: code.delete()

            return Response({"message": {"detail": _("A password has been successfully set!")}}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ChangeUserEmail(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangeEmailSerializer

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        serializer = self.serializer_class(data=data, context={'request': self.request})
        user = self.request.user
        if not serializer.is_valid():
            errors = {"message": {"detail": _("Request body is invalid.")}}
            for field, error in serializer.errors.items():
                errors = {"message": {"detail": _(error[0])}}
                break
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
            # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        confirm_code = ConfirmCode.objects.filter(user=user, new_email=data['new_email'].lower()).first()
        if not confirm_code:
            confirm_code = ConfirmCode(user=user, new_email=data['new_email'].lower())
        confirm_code.code = randint(1111111111, 9999999999)
        confirm_code.expiring_date = now() + timedelta(hours=3)
        confirm_code.save()

        # change link
        link = f'https://{settings.FRONT_DOMAIN}/settings/{confirm_code.code}'
        msg = MIMEMultipart('alternative')  # this is special format for email messages

        subj = _('Confirm email - DO NOT REPLY TO THIS MESSAGE')
        msg['Subject'] = str(subj)
        _from = f"InHome Dataforest <{settings.EMAIL_HOST_USER}>"
        msg['From'] = _from
        msg['To'] = data['new_email']
        html = 'confirm_email.html'
        """ Encoding html file to the required format for gmail """
        html = render_to_string(html, {'link': link})
        part2 = MIMEText(html, 'html')
        msg.attach(part2)
        """ SMTP connection is more secure than django default send_mail """
        server = SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.sendmail(settings.EMAIL_HOST, data['new_email'], msg.as_string())
        server.quit()
        return Response({"message": {"detail": _("Confirmation email was sent")}}, status=status.HTTP_200_OK)

    def get(self, request):
        code = request.query_params.get('code', '')
        if not all([code, code.isdigit()]):
            return Response({"message": {"detail": _('provide digital code')},
                             "status_code": 400}, status=status.HTTP_400_BAD_REQUEST)

        confirm_code = ConfirmCode.objects.filter(code=code, expiring_date__gt=now(), new_email__isnull=False).first()
        if not all([code, confirm_code]):
            return Response(
                {"message": {"detail": _("Email not confirmed. Confirmation code is expired or does not exist.")},
                 "status_code": 400}, status=status.HTTP_400_BAD_REQUEST)

        if confirm_code.new_email is not None:
            user = confirm_code.user
            user.email = confirm_code.new_email
            user.save()
            confirm_code.delete()

        token = RefreshToken.for_user(user)
        response = dict()
        response['refresh'] = str(token)
        response['access'] = str(token.access_token)
        response['user'] = FullUserInfoSerializer(user, context={'request': self.request}).data
        return Response(response)

