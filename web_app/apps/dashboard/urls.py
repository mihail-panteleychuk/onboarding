from django.urls import path

from apps.dashboard.views import DefaultDashboardView

urlpatterns = [
    path("", DefaultDashboardView.as_view(), name="Get default info by user"),
]
