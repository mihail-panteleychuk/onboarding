from django.urls import include, path
from rest_framework import routers

from .views import AdminPanelUsersViewSet, ListOfRolesView

Router = routers.DefaultRouter()
Router.register("users", AdminPanelUsersViewSet)


urlpatterns = [
    path("users/roles/", ListOfRolesView.as_view(), name="Get list of available roles"),
    path("", include(Router.urls)),
]
