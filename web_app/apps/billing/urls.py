"""URL configuration for billing app."""

from django.urls import include, path
from rest_framework import routers

from apps.billing.views import (
    BalanceTopUpView,
    BalanceTransactionsView,
    BalanceView,
    ServiceRequestViewSet,
    ServiceTypeViewSet,
)

router = routers.DefaultRouter()
router.register("service-types", ServiceTypeViewSet, basename="service-type")
router.register("requests", ServiceRequestViewSet, basename="service-request")

urlpatterns = [
    path("balance/", BalanceView.as_view(), name="balance"),
    path("balance/transactions/", BalanceTransactionsView.as_view(), name="balance-transactions"),
    path("balance/topup/", BalanceTopUpView.as_view(), name="balance-topup"),
    path("", include(router.urls)),
]
