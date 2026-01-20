from rest_framework import routers
from django.urls import path, include

from .views import (UserViewSet, CountryListView, ChangeUserEmail, DetectRequestIP)

router = routers.DefaultRouter()
router.register('', UserViewSet)
router.register('country-list', CountryListView)


urlpatterns = [
    path('', include(router.urls)),
    path('change-email/', ChangeUserEmail.as_view(), name='Change user email from settings'),
    path('get_country/', DetectRequestIP.as_view(), name="Get user country by request IP"),

]
