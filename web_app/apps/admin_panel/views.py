from django.contrib.auth import get_user_model
from django_filters import rest_framework as rest_filter
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.admin_panel.serializers import (
    AdminPanelUserCreateSerializer,
    AdminPanelUserUpdateSerializer,
)
from apps.core.permissions import IsCustomAdminOrManagerUser


class AdminPanelUsersViewSet(viewsets.ModelViewSet):
    queryset = get_user_model().objects.all()
    serializer_class = AdminPanelUserCreateSerializer
    permission_classes = (IsCustomAdminOrManagerUser,)

    filter_backends = (
        filters.SearchFilter,
        rest_filter.DjangoFilterBackend,
        filters.OrderingFilter,
    )
    ordering_fields = (
        "id",
        "first_name",
        "last_name",
        "email",
        "created",
    )
    ordering = ("-created",)
    search_fields = ["$first_name", "$last_name", "$email"]
    filter_fields = ("role",)
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action != "create":
            self.serializer_class = AdminPanelUserUpdateSerializer
        return super().get_serializer_class()

    @action(
        detail=True,
        methods=["DELETE", "POST"],
        url_path="delete",
        permission_classes=(IsCustomAdminOrManagerUser,),
        serializer_class=AdminPanelUserUpdateSerializer,
    )
    def block_unblock_user(self, request, *args, **kwargs):
        instance = self.get_object()
        deleted = request.method == "DELETE"
        instance.is_deleted = deleted
        instance.is_active = not deleted
        instance.save()
        serializer = AdminPanelUserUpdateSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class ListOfRolesView(generics.RetrieveAPIView):
    queryset = get_user_model().objects.none()
    permission_classes = (IsCustomAdminOrManagerUser,)
    serializer_class = None  # Не используем serializer, переопределяем get_serializer_class

    def get_serializer_class(self):
        """Override to avoid Swagger schema generation error."""
        return None

    def get(self, request, *args, **kwargs):
        roles = dict(get_user_model().UserRoleChoices.choices)
        data = [{"id": key, "title": value} for key, value in roles.items()]
        return Response(data, status=status.HTTP_200_OK)
