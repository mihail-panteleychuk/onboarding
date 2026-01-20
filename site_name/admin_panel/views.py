import logging

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as rest_filter
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from config.permissions import IsCustomAdminOrManagerUser
from .models import *
from .serializers import *

logger = logging.getLogger("DJANGO")


class AdminPanelUsersViewSet(viewsets.ModelViewSet):
    queryset = get_user_model().objects.all()
    serializer_class = AdminPanelUserCreateSerializer
    permission_classes = (IsAuthenticated, IsCustomAdminOrManagerUser)

    filter_backends = (filters.SearchFilter, rest_filter.DjangoFilterBackend, filters.OrderingFilter, )
    ordering_fields = ('id', 'first_name', 'last_name', 'email', 'created', )
    ordering = ('-created', )
    search_fields = ['$first_name', '$last_name', '$email']
    filter_fields = ('role', )
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.action != 'create':
            self.serializer_class = AdminPanelUserUpdateSerializer

        return super(AdminPanelUsersViewSet,self).get_serializer_class()


class ListOfRolesView(generics.RetrieveAPIView):
    queryset = get_user_model().objects.none()
    permission_classes = (IsAuthenticated, IsCustomAdminOrManagerUser)

    def get(self, request, *args,**kwargs):
        roles = dict(get_user_model().ROLE_CHOICES)

        data = [
            {
                'id': key,
                'title': value
            }
            for key, value in roles.items()
        ]


        return Response(data, status=status.HTTP_200_OK)
