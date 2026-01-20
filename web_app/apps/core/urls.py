from django.urls import path

from apps.core.views import heartbeat, test_decrypt, test_dummy_task

urlpatterns = [
    path("heartbeat/", heartbeat),
    path("test_decrypt/", test_decrypt),
    path("test_dummy_task/", test_dummy_task),
]
