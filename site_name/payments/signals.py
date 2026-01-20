

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import BillingAddress
from .utils import create_stripe_customer, sync_user_data, update_customer_billing_info, remove_customer, cancel_all_user_subscriptions
UserModel = get_user_model()


# POST USER CREATE SIGNAL
@receiver(post_save, sender=get_user_model())
def create_or_update_customer_in_stripe(sender, instance, created, **kwargs):
    """
        Add other default related objects creating on new user creating if needeed
        example: create user profile on payments service
    """
    if isinstance(instance, UserModel):
        if created:
            create_stripe_customer(instance)
        else:
            try:
                if instance.is_deleted and instance.payment_service_user_id:
                    cancel_all_user_subscriptions(instance.payment_service_user_id)
                    instance.payment_service_user_id = None
                    instance.save()
                sync_user_data(instance)
            except:
                instance.payment_service_user_id = None
                instance.save()

@receiver(post_delete, sender=get_user_model())
def remove_customer_from_stripe(sender, instance, **kwargs):
    if isinstance(instance, UserModel) and instance.payment_service_user_id:
        try:
            cancel_all_user_subscriptions(instance.payment_service_user_id)
            remove_customer(instance.payment_service_user_id)
        except:
            pass

@receiver(post_save, sender=BillingAddress)
def update_billing_address_in_stripe(sender, instance, created, **kwargs):
    if isinstance(instance, BillingAddress):
        update_customer_billing_info(instance)

