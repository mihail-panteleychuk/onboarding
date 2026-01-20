from django.urls import path

from .views import DefaultDashboardView

urlpatterns = [
    path("", DefaultDashboardView.as_view(), name="Get default info by user"),
]
