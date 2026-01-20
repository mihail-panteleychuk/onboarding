import logging
from typing import Callable, Type

from django.contrib.auth import get_user_model
from django.db.models import Model
from django.db.models.signals import (
    ModelSignal,
    post_save,
    post_delete,
)
from django.test.testcases import TestCase
from apps.payments import signals
from apps.payments.models import BillingAddress

logger = logging.getLogger(__name__)
UserModel = get_user_model()


class SkipStripeSignalsTestCase(TestCase):
    signals: tuple[tuple[ModelSignal, Callable, Type[Model]]] = (
        (post_save, signals.create_or_update_customer_in_stripe, UserModel),
        (post_delete, signals.remove_customer_from_stripe, UserModel),
        (post_save, signals.update_billing_address_in_stripe, BillingAddress),
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for signal, receiver, sender in cls.signals:
            signal.disconnect(receiver=receiver, sender=sender)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        for signal, receiver, sender in cls.signals:
            signal.connect(receiver=receiver, sender=sender)
