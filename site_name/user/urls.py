from django.urls import include, path
from rest_framework import routers

from site_name.user.views import ChangeUserEmail, CountryListView, DetectRequestIP, UserViewSet

router = routers.DefaultRouter()
router.register("country-list", CountryListView)
router.register("", UserViewSet)


urlpatterns = [
    path("change-email/", ChangeUserEmail.as_view(), name="Change user email from settings"),
    path("get_country/", DetectRequestIP.as_view(), name="Get user country by request IP"),
    path("", include(router.urls)),
]
