from rest_framework import routers
from django.urls import path, include

from .views import (UserViewSet, ChangeUserEmail)

router = routers.DefaultRouter()
router.register('', UserViewSet)


urlpatterns = [
    path('change-email/', ChangeUserEmail.as_view(), name='Change user email from settings'),
    path('', include(router.urls)),
]
