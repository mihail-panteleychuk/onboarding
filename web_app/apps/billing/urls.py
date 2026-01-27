"""URL configuration for billing app."""

from django.urls import include, path
from rest_framework import routers

from apps.billing.views import (
    BalanceTopUpView,
    BalanceTransactionsExportView,
    BalanceTransactionsView,
    BalanceView,
    ServiceRequestViewSet,
    ServiceTypeViewSet,
)

router = routers.DefaultRouter()
router.include_root_view = False  
router.register("service-types", ServiceTypeViewSet, basename="service-type")
router.register("requests", ServiceRequestViewSet, basename="service-request")

urlpatterns = [
    path("balance/", BalanceView.as_view(), name="balance"),
    path("balance/transactions/", BalanceTransactionsView.as_view(), name="balance-transactions"),
    path("balance/transactions/export/", BalanceTransactionsExportView.as_view(), name="balance-transactions-export"),
    path("balance/topup/", BalanceTopUpView.as_view(), name="balance-topup"),
    path("", include(router.urls)),
]
