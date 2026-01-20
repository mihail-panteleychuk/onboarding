from core.exceptions import CustomAPIException
from django.utils.translation import gettext_lazy as _
from rest_framework import status

CANNOT_DETACH_LAST_SOCIAL_FROM_ACCOUNT_EXCEPTION = CustomAPIException(
    detail={
        "detail": _(
            "Action can not be complete. You do not have a password yet, therefore your "
            "account can be lost if you disconnect. Create a password, and you will "
            "be able to disconnect the social platform of your choice."
        )
    },
    status=status.HTTP_400_BAD_REQUEST,
)

CODE_EXPIRED_OR_INVALID_EXCEPTION = CustomAPIException(
    detail={"detail": _("Email not confirmed. Confirmation code is expired or does not exist.")},
    status=status.HTTP_400_BAD_REQUEST,
)

BLOCKED_ACCOUNT_EXCEPTION = CustomAPIException(
    detail={"detail": ("Your account is blocked. To unblock it please contact Support.")},
    code=status.HTTP_400_BAD_REQUEST,
)


ACCOUNT_IS_NOT_ACTIVE_EXCEPTION = CustomAPIException(
    detail={"detail": "No active account found with the given credentials."},
    code=status.HTTP_400_BAD_REQUEST,
)


INVALID_EMAIL_EXCEPTION = CustomAPIException(
    {"detail": _("Please provide a valid email address")},
    status=status.HTTP_400_BAD_REQUEST,
)


INVALID_USER_DATA_EXCEPTION = CustomAPIException(
    detail={"detail": _("Please provide first name, last name and email")},
    status=status.HTTP_400_BAD_REQUEST,
)
