from django.urls import include, path
from rest_framework import routers

from apps.payments.views import (
    CreateCardView,
    CreateSubscriptionView,
    InvoiceViewSet,
    StripeWebhookView,
    UpdateSubscriptionView,
)

router = routers.DefaultRouter()
router.register("invoices", InvoiceViewSet)


urlpatterns = [
    path("create_card", CreateCardView.as_view()),
    path("subscribe", CreateSubscriptionView.as_view()),
    path("subscription/change", UpdateSubscriptionView.as_view()),
    path("stripe/webhook/", StripeWebhookView.as_view()),
    path("", include(router.urls)),
]
