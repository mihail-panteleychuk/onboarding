from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission

UserModel = get_user_model()


class IsCustomAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.role in [UserModel.ADMIN])
