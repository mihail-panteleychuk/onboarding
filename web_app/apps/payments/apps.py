from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = "apps.payments"

    def ready(self):
        from . import signals  # noqa: ABS101
