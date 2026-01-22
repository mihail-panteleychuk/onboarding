import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.payments.models import BillingAddress
from apps.payments.utils import (
    cancel_all_user_subscriptions,
    create_stripe_customer,
    remove_customer,
    sync_user_data,
    update_customer_billing_info,
)

stripe_logger = logging.getLogger("stripe")

UserModel = get_user_model()


@receiver(post_save, sender=UserModel)
def create_or_update_customer_in_stripe(sender, instance, created, **kwargs):
    """
    Handles the creation or updating of a customer in Stripe when a UserModel instance is saved.

    On creation of a new user, a corresponding Stripe customer is created.
    On update, if the user is marked as deleted, all their Stripe subscriptions are canceled.
    Otherwise, user data is synced with Stripe.
    """
    if isinstance(instance, UserModel):
        if created:
            try:
                create_stripe_customer(instance)
            except Exception as e:  # noqa: E722
                # In local development, Stripe keys might be missing.
                # Do not interrupt user creation, but log the error.
                stripe_logger.warning(
                    f"Failed to create Stripe customer for user {instance.id}: {str(e)}"
                )
        else:
            try:
                if instance.is_deleted and instance.payment_service_user_id:
                    cancel_all_user_subscriptions(instance.payment_service_user_id)
                    instance.payment_service_user_id = None
                    instance.save()
                sync_user_data(instance)
            except Exception as e:  # noqa: E722
                stripe_logger.warning(
                    f"Failed to sync Stripe data for user {instance.id}: {str(e)}"
                )
                instance.payment_service_user_id = None
                instance.save()


@receiver(post_delete, sender=UserModel)
def remove_customer_from_stripe(sender, instance, **kwargs):
    """
    Handles the removal of a customer from Stripe when a UserModel instance is deleted.

    Cancels all subscriptions and removes the customer from Stripe if they have a payment service user ID.
    """
    if isinstance(instance, UserModel) and instance.payment_service_user_id:
        try:
            cancel_all_user_subscriptions(instance.payment_service_user_id)
            remove_customer(instance.payment_service_user_id)
        except Exception as e:  # noqa: E722
            stripe_logger.warning(
                f"Failed to remove Stripe customer {instance.payment_service_user_id}: {str(e)}"
            )


@receiver(post_save, sender=BillingAddress)
def update_billing_address_in_stripe(sender, instance, created, **kwargs):
    """
    Updates the billing address in Stripe when a BillingAddress instance is saved.

    If a BillingAddress instance is saved, it triggers an update of the corresponding billing information in Stripe.
    """
    if isinstance(instance, BillingAddress):
        update_customer_billing_info(instance)
