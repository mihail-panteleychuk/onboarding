from django.urls import include, path
from rest_framework import routers

from apps.subscription.views import PlanViewSet, SubscriptionView

router = routers.DefaultRouter()
router.register("plan", PlanViewSet)


urlpatterns = [
    path("", include(router.urls)),
    path("<str:filter>/", SubscriptionView.as_view()),
]
