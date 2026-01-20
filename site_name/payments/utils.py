import json
import logging
import traceback
from datetime import datetime

import stripe
from admin_panel.models import Settings
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from stripe import error as stripe_errors
from subscription.constants import (STATUS_CANCELED, STATUS_FAILED,
                                    STATUS_PAID, STATUS_PENDING, STATUS_TRIAL)
from subscription.models import Plan, Subscription

from .models import Card, Invoice, SubscriptionType

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe_logger = logging.getLogger('stripe')



def stripe_exception_decorator(func):
    """
    Deforator for handling payment service errors
    """
    def inner_function(*args, **kwargs):
        e_m = ''
        try:
            return func(*args, **kwargs)
        except stripe_errors.CardError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'CardError occurred'
            resp = {"message": {"detail": e_m}}
        except stripe_errors.OperationFailedError as e:
            e_m = e
            trace = traceback.format_exc()
            message = 'Operation failed'
            resp = {"message": {"detail": "Operation cannot be processed"}}
        except stripe_errors.InvalidRequestError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'Invalid request'
            resp =  {"message": {"detail": e_m}}
        except (stripe_errors.AuthenticationError, stripe_errors.PermissionError) as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'Auth error occurred'
            resp =  {"message": {"detail": e_m}}
        except stripe_errors.RateLimitError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'RateLimitError error occurred'
            resp =  {"message": {"detail": e_m}}
        except stripe_errors.StripeError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'Stripe general error'
            resp =  {"message": {"detail": e_m}}
        except Exception as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'Unexpected exception'
            resp = {"message": {"detail": _("Something went wrong due processing your data!")}}

        args = str(args)
        kwargs = str(kwargs)
        stripe_logger.error(
                json.dumps({
                    'timestamp': str(datetime.now()),
                    'message': message,
                    "error": e_m, "traceback": trace,
                    "args": args, "kwargs": kwargs}
                )
            )
        return resp
    return inner_function

def retrieve_coupon(coupon_id):
    #! add usage os this func!!
    """Docs: https://stripe.com/docs/api/coupons/retrieve?lang=python"""
    result = stripe.Coupon.retrieve(coupon_id)
    return result.coupon

@stripe_exception_decorator
def create_coupon(coupon):
    try:
        discount = Settings.objects.get('discount').get_value()
    except:
        discount = 10.0
    result = stripe.Coupon.create({
        "id" : coupon,
        "name" : f"Refershion {coupon}",
        "percent_off" : discount,
        "duration" : "forever"
    })

    # result = chargebee.Coupon.retrieve(coupon_id)
    return stripe.util.convert_to_dict(result)



def get_status(status):
    """Mapping stripe statuses to our custom status models (see: subscription.constants)"""
    statuses_mapping = {
        "paid": STATUS_PAID,
        "active": STATUS_PAID,
        'trialing': STATUS_TRIAL,
        "canceled": STATUS_CANCELED,
        "unpaid": STATUS_FAILED,
        "incomplete_expired": STATUS_FAILED,
        "incomplete": STATUS_PENDING,
        "past_due": STATUS_PENDING,
        ##### invoice statuses
        "draft": "", #! invoice
        "open": STATUS_PENDING,
        "void": STATUS_CANCELED,

    }
    return statuses_mapping.get(status, STATUS_FAILED)







# =======================================================================================
# =========================== STRIPE CUSTOMER PROCESSING ================================
# =======================================================================================
@stripe_exception_decorator
def create_stripe_customer(user):
    """Creating customer account on chargebee for new user and saving its customer_id

    Args:
        user (`user.User`): User model object
    """
    result = stripe.Customer.create(
        email=user.email,
        name=user.full_name
    )
    user.payment_service_user_id = result.id
    user.save()


@stripe_exception_decorator
def retreive_customer(user):
    customer = stripe.Customer.retrieve(user.payment_service_user_id)
    return customer


@stripe_exception_decorator
def remove_customer(customer_id):
    result = stripe.Customer.delete(customer_id)
    return result.deleted


@stripe_exception_decorator
def sync_user_data(user):
    stripe.Customer.modify(
        user.payment_service_user_id,
        email = user.email,
        name = user.full_name,
        preferred_locales = user.language
    )


@stripe_exception_decorator
def update_customer_billing_info(billing_object, _type='billing'):
    """Updating user billing info on chargebee

    Args:
        billing_object (`user.BillingAddress`): updated billing address object
    """
    if _type == 'billing':
        stripe.Customer.modify(
            billing_object.user.payment_service_user_id,
            address={
                "city" : billing_object.city,
                "country": billing_object.country.country_code,
                "line1" : billing_object.address,
                "line2" : None,
                "postal_code" : billing_object.postal_code,
                "state" : billing_object.state,
            }
        )
    # # updating billing company details
    # else:
    #     stripe.Customer.modify(
    #         billing_object.user.payment_service_user_id,
    #         {
    #             "vat_number": billing_object.VAT,
    #             "billing_address" : {
    #                 "company" : billing_object.name,
    #                 "line1" : billing_object.address_line_1,
    #                 "line2" : billing_object.address_line_2,
    #                 "city" : billing_object.city,
    #                 "state" : billing_object.state,
    #                 "zip" : billing_object.postal_code,
    #                 "country" : billing_object.country.country_code
    #             }
    #         }
    #     )







# =======================================================================================
# =========================== STRIPE SUBSCRIPTIONS PROCESSING ===========================
# =======================================================================================
@stripe_exception_decorator
def create_subscriptions_for_user(user, plan_id, coupon=None):
    """Initial subscription creating from onboarding/checkout
    Args:
        user (`user.User`): User object, who is subscribing.
        plan_id (`str`): identifier of selected plan for subscription
        coupon (`str`, optional): discount code if coupon is applied. Defaults to None.

    Return:
        created_subscription (`subscription.models.Subscription`): subscription object
    """

    try:
        plan = Plan.objects.get(pk=plan_id)
    except:
        return {"message": {"detail": "No plan found"}}

    stripe_subscription = stripe.Subscription.create(
            customer=user.payment_service_user_id,
            items = [
                {'price': plan.payment_plan_id}
            ],
            coupon = coupon,
            expand=['latest_invoice']
        )


    created_subscription = Subscription(
        user=user,
        plan=plan,
        payment_subscription_id=stripe_subscription.id,
        paid_amount = stripe_subscription.latest_invoice.amount_paid,
        start_date = datetime.fromtimestamp(stripe_subscription.current_period_start, tz=timezone.utc),
        next_payment_date = datetime.fromtimestamp(stripe_subscription.current_period_end, tz=timezone.utc),
        status=get_status(stripe_subscription.status)
    )
    created_subscription.save()

    if not created_subscription:
        return {"message": {"detail": "Subscription creating failed."}}

    return created_subscription


#! continue from here
@stripe_exception_decorator
def update_subscription(current_sub, new_plan, force_update=False, coupon=None, intent_id=None):
    """Creating scheduled(or not) changes for user subscriptions

    Args:
        current_sub (`subscription.Subscription`): Current subscription object for which changes are applying
        new_plan (`subscription.Plan`): New plan selected by user for changing
        force_update (`bool`, optional): Flag to identify whether create scheduled changes or apply changes immediately. Defaults to False.
        coupon (`str`, optional): discount code if coupon is applied. Defaults to None.
    """
    coupons = [coupon, ] if coupon else None
    intent_body = {}
    if intent_id:
        intent_body = {'payment_intent': {"id": intent_id}}

    chargebee.configure(settings.CHARGEBEE_API_KEY, settings.CHARGEBEE_SITE_NAME)
    body = {
        "auto_collection": "on",
        "replace_items_list": True,
        "replace_coupon_list": True,
        "coupon_ids": coupons,
    }
    if new_plan :
        body.update({
            "subscription_items" : [{
                    "item_price_id" : new_plan.payment_plan_id,
                }]
        })

    if force_update:
        body.update({
            "invoice_immediately" : True,
            "has_scheduled_changes": False,
            "change_option": "immediately",
            "end_of_term": False,
        })
        body.update(intent_body)
    else:

        body.update(
            {
                "invoice_immediately" : False,
                "has_scheduled_changes": True,
                "change_option": "end_of_term",
                "end_of_term": True,
                # "trial_end_action": 'activate_subscription'

            }
        )
    result = chargebee.Subscription.update_for_items(current_sub.payment_subscription_id, body)

    return result.subscription


@stripe_exception_decorator
def remove_scheduled_changes(current_sub):
    """Canceling schedule changes on subscription

    Args:
        current_sub (`subscription.Subscription`): Subscription object
    """
    chargebee.configure(settings.CHARGEBEE_API_KEY, settings.CHARGEBEE_SITE_NAME)
    result = chargebee.Subscription.remove_scheduled_changes(current_sub.payment_subscription_id)
    return result.subscription


@stripe_exception_decorator
def schedule_subscription_cancelation(subscription):
    chargebee.configure(settings.CHARGEBEE_API_KEY, settings.CHARGEBEE_SITE_NAME)
    # result = chargebee.Subscription.remove_scheduled_cancellation(subscription.payment_subscription_id)
    result = chargebee.Subscription.cancel_for_items(subscription.payment_subscription_id,{
        "end_of_term" : True
    })
    return result.subscription

@stripe_exception_decorator
def cancel_schedule_subscription_cancelation(subscription):
    chargebee.configure(settings.CHARGEBEE_API_KEY, settings.CHARGEBEE_SITE_NAME)
    result = chargebee.Subscription.remove_scheduled_cancellation(subscription.payment_subscription_id)
    # result = chargebee.Subscription.cancel_for_items(subscription.payment_subscription_id,{
    #     "end_of_term" : True
    # })

    return result.subscription




# =======================================================================================
# =========================== STRIPE PAYMENTS PROCESSING ================================
# =======================================================================================
@stripe_exception_decorator
def create_intent(user, amount, payment_method_type="card"):
    result = stripe.PaymentIntent.create(
        amount= amount if amount != 0 else 1,
        currency="usd",
        payment_method_types=[payment_method_type, ],
        confirm=True,
        customer=user.payment_service_user_id,
    )

    return stripe.util.convert_to_dict(result)


@stripe_exception_decorator
def create_card(user, type, **kwargs):

    if card_token:=kwargs.get('card_token'):
        result = stripe.Customer.create_source(
            user.payment_service_user_id,
            source=card_token,
        )
    else:
        raise Exception("HZ what to do??!") #!  replace
    return result



@stripe_exception_decorator
def replace_card(customer_id, intent_id):
    chargebee.configure(settings.CHARGEBEE_API_KEY, settings.CHARGEBEE_SITE_NAME)

    result = chargebee.PaymentSource.create_using_payment_intent({
        "customer_id" : customer_id,
        "replace_primary_payment_source": True,
        "payment_intent" : {
            "id" : intent_id
        }
    })
    return result
