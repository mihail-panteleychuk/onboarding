from django.urls import path

from site_name.dashboard.views import DefaultDashboardView

urlpatterns = [
    path("", DefaultDashboardView.as_view(), name="Get default info by user"),
]
