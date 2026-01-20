from django.urls import path

from apps.core import views

urlpatterns = [
    path("heartbeat/", views.heartbeat),
    path("test_decrypt/", views.view_test_decrypt),
    path("test_dummy_task/", views.view_test_dummy_task),
    path("test_dummy_exception/", views.view_test_dummy_exception),
]
