from django.urls import include, path
from rest_framework import routers

from .views import ChangeUserEmail, UserViewSet

router = routers.DefaultRouter()
router.register("", UserViewSet)


urlpatterns = [
    path("change-email/", ChangeUserEmail.as_view(), name="Change user email from settings"),
    path("", include(router.urls)),
]
