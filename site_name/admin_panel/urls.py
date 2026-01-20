from django.urls import path, include
from .views import (AdminPanelUsersViewSet, ListOfRolesView)
from rest_framework import routers


Router = routers.DefaultRouter()
Router.register('users', AdminPanelUsersViewSet)


urlpatterns = [
    path('users/roles/', ListOfRolesView.as_view(), name='Get list of available roles'),
    path('', include(Router.urls)),


]
