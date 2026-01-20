from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class PaymentsConfig(AppConfig):
    name = "apps.payments"

    def ready(self):
        from . import signals  # noqa: ABS101

        # Explicitly connect a signal handler.
        post_save.connect(signals.create_or_update_customer_in_stripe)
        post_delete.connect(signals.remove_customer_from_stripe)
        post_save.connect(signals.update_billing_address_in_stripe)
