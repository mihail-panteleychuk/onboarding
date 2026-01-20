from django.urls import include, path
from rest_framework import routers

from apps.admin_panel.views import AdminPanelUsersViewSet, ListOfRolesView

router = routers.DefaultRouter()
router.register("users", AdminPanelUsersViewSet)


urlpatterns = [
    path("users/roles/", ListOfRolesView.as_view(), name="Get list of available roles"),
    path("", include(router.urls)),
]
