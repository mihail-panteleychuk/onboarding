from django.urls import path, include

from .views import *
from rest_framework import routers


Router = routers.DefaultRouter()
Router.register('invoices', InvoiceViewSet)


urlpatterns = [
    path('create_card', CreateCardView.as_view()),
    path('subscribe', CreateSubscriptionView.as_view()),
    path('subscription/change', UpdateSubscriptionView.as_view()),
    path('stripe/webhook/', StripeWebhookView.as_view()),
    path('', include(Router.urls)),


]

