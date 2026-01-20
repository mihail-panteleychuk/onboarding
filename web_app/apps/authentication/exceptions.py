from django.utils.translation import gettext_lazy as _
from rest_framework import status

from apps.core.exceptions import CustomAPIException


class CannotDetachLastSocialFromAccountException(CustomAPIException):
    detail = {
        "detail": _(
            "Action can not be complete. You do not have a password yet, therefore your "
            "account can be lost if you disconnect. Create a password, and you will "
            "be able to disconnect the social platform of your choice.",
        ),
    }
    code = status.HTTP_400_BAD_REQUEST


class CodeExpiredOrInvalidException(CustomAPIException):
    detail = {"detail": _("Email not confirmed. Confirmation code is expired or does not exist.")}
    code = status.HTTP_400_BAD_REQUEST


class BlockedAccountException(CustomAPIException):
    detail = {"detail": _("Your account is blocked. To unblock it please contact Support.")}
    code = status.HTTP_400_BAD_REQUEST


class AccountIsNotActiveException(CustomAPIException):
    detail = {"detail": _("No active account found with the given credentials.")}
    code = status.HTTP_400_BAD_REQUEST


class InvalidEmailException(CustomAPIException):
    detail = {"detail": _("Please provide a valid email address")}
    code = status.HTTP_400_BAD_REQUEST


class InvalidUserDataException(CustomAPIException):
    detail = {"detail": _("Please provide first name, last name and email")}
    code = status.HTTP_400_BAD_REQUEST
