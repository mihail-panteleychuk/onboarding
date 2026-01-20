import json
import logging
import traceback
from datetime import datetime

import stripe
from admin_panel.models import Settings
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from stripe import error as stripe_errors
from subscription.constants import *

from subscription.models import Plan, Subscription

from .models import *

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe_logger = logging.getLogger('stripe')
from django.utils.timezone import now
from core.exceptions import CustomAPIException, APIException


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
            resp = {"detail": e_m}
        except stripe_errors.APIError as e:
            e_m = e
            trace = traceback.format_exc()
            message = 'Operation failed'
            resp = {"detail": "Operation cannot be processed"}
        except stripe_errors.InvalidRequestError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'Invalid request'
            resp =  {"detail": e_m}
        except (stripe_errors.AuthenticationError, stripe_errors.PermissionError) as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'Auth error occurred'
            resp =  {"detail": e_m}
        except stripe_errors.RateLimitError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'RateLimitError error occurred'
            resp =  {"detail": e_m}
        except stripe_errors.StripeError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'Stripe general error'
            resp =  {"detail": e_m}
        except CustomAPIException as e:
            e_m = str(e.detail)
            trace = traceback.format_exc()
            message = 'APIException handling'
            resp = e
        except APIException as e:
            e = CustomAPIException(detail=e.detail, code=e.status_code)
            e_m = str(e.detail)
            trace = traceback.format_exc()
            message = 'APIException handling'
            resp = e
        except Exception as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = 'Unexpected exception'
            resp = {"detail": _("Something went wrong due processing your data!")}

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
        if isinstance(resp, dict) and 'detail' in resp.keys():
            raise CustomAPIException(detail=resp, code=status.HTTP_400_BAD_REQUEST)
        else:
            raise resp
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


@stripe_exception_decorator
def retrieve_stripe_account_billing():
    # Stripe is returning data about bussiness profile only in `Live Mode`. So for development environment - data is hardcoded
    if settings.IS_PRODUCTION:
        data = stripe.Account.retrieve(settings.STRIPE_ACCOUNT_ID)
        return data['business_profile']
    else:
        return settings.TEST_BUSSINESS_PROFILE


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
        "void": STATUS_FAILED,

    }
    return statuses_mapping.get(status, STATUS_FAILED)



# =======================================================================================
# =======================================================================================
# =========================== STRIPE CUSTOMER PROCESSING ================================
# =======================================================================================
# =======================================================================================
@stripe_exception_decorator
def create_stripe_customer(user):
    """Creating customer account on chargebee for new user and saving its customer_id

    Args:
        user (`user.User`): User model object
    """
    if not user.payment_service_user_id:
        result = stripe.Customer.create(
            email=user.email,
            name=user.full_name,
            metadata = {"ID": user.id }
        )
        user.payment_service_user_id = result.id
        user.save()


@stripe_exception_decorator
def cancel_all_user_subscriptions(customer_id):
    subscriptions = stripe.Subscription.list(
        customer=customer_id,
        status='active',
        limit=100)

    for subscription in subscriptions:
        stripe.Subscription.delete(
            subscription['id'],
        )

def cancel_subscription(subscription_id):
    stripe.Subscription.delete(subscription_id)

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
    if user.payment_service_user_id:
        if user.phone_code and user.phone_code.code and user.phone:
            phone_number = f"{user.phone_code.code}{user.phone}"
        else:
            phone_number = None

        stripe.Customer.modify(
            user.payment_service_user_id,
            email = user.email,
            name = user.full_name,
            phone = phone_number,
            preferred_locales = [user.language, ]
        )


@stripe_exception_decorator
def update_customer_billing_info(billing_object, _type='billing'):
    """Updating user billing info on chargebee

    Args:
        billing_object (`user.BillingAddress`): updated billing address object
    """
    if _type == 'billing':
        stripe.Customer.modify(
            billing_object.card.user.payment_service_user_id,
            address={
                "city" : billing_object.city,
                "country": billing_object.country.country_code,
                "line1" : billing_object.address_line_1,
                "line2" : billing_object.address_line_2,
                "postal_code" : billing_object.postal_code,
                "state" : billing_object.state,
            }
        )





# =======================================================================================
# =========================== STRIPE SUBSCRIPTIONS PROCESSING ===========================
# =======================================================================================


def __handle_stripe_subscriptions_response(user, stripe_response, created_sub=None, created=True, redirect_url=None):
    if created_sub:
        write_invoice(stripe_response, stripe_response['latest_invoice'], created_sub)

    if stripe_response['status'] in ['past_due', 'incomplete'] or stripe_response.get('pending_update'):
        invoice = stripe.Invoice.retrieve(stripe_response['latest_invoice']['id'])
        if invoice['status'] == 'open':
            payment_intent = stripe.PaymentIntent.retrieve(invoice['payment_intent'])
            if payment_intent.get('next_action'):
                # stripe_logger.info('Creating redirect link for successful confirmation of 3D secure')
                try:
                    success_url = redirect_url or settings.STRIPE_ORDER_SUCCESS_URL # if created else settings.STRIPE_UPDATE_SUCCESS_URL
                    intent = stripe.PaymentIntent.confirm(
                        invoice['payment_intent'],
                        payment_method=payment_intent['payment_method'],
                        return_url=success_url + payment_intent['client_secret']
                    )

                    payment_required_link = intent['next_action']['redirect_to_url']['url']
                    return payment_required_link
                except Exception as error:
                    raise CustomAPIException(detail={'detail': error}, code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        """ this error will occur only if stripe will change something in their api """
        # stripe_logger.error('Got an unexpected error with response format of invoice(370 line, payment/views.py)')
        raise CustomAPIException(detail={'detail': 'Got an unexpected error'}, code=status.HTTP_500_INTERNAL_SERVER_ERROR)



def __user_sub_already_exists(user):
    subscriptions = stripe.Subscription.list(
        customer=user.payment_service_user_id,
        status='active',
        limit=100)
    return len(subscriptions['data']) > 0

@stripe_exception_decorator
def create_subscription_for_user(user, plan_id, coupon=None, redirect_url=None):
    """Initial subscription creating from onboarding/checkout
    Args:
        user (`user.User`): User object, who is subscribing.
        plan_id (`str`): identifier of selected plan for subscription
        coupon (`str`, optional): discount code if coupon is applied. Defaults to None.

    Return:
        created_subscription (`subscription.models.Subscription`): subscription object
    """

    if __user_sub_already_exists(user):
        raise CustomAPIException(detail={'detail': 'User already has a subscription.'}, code=status.HTTP_409_CONFLICT)

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
            expand=['latest_invoice'],
            payment_behavior='allow_incomplete'
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

    redirect_link = __handle_stripe_subscriptions_response(user, stripe_subscription, created_subscription, redirect_url=redirect_url)

    return created_subscription, redirect_link


def write_invoice(stripe_subscription, invoice_source_data, created_sub):
    """
    Recording an invoice depending on payment service.

    :param user_payment_service: active payment method of the user.
    :param service_subscription: subscription data received from the payment service.
    :param source_data: data that is filled in on the side of the payment service, if any.
    :param invoice_status: manual setting of invoice status.
    """

    invoice_number = invoice_source_data['number']
    invoice_status = get_status(invoice_source_data['status'])
    subscription_plan = stripe_subscription['plan']['id']


    services = invoice_source_data['lines']['data']

    invoice_data = {
        'status': invoice_status,
        'user': created_sub.user,
        'total': invoice_source_data['total'],
        'issued_date': now().date(),
        'issued': now(),
        'card': created_sub.user.cards.filter(active=True).latest('created'),
        'user': created_sub.user,
    }

    invoice = Invoice.objects.filter(invoice_id=invoice_number).first()
    if not invoice and invoice_number:
        invoice = Invoice.objects.create(invoice_id=invoice_number, **invoice_data)
        invoice.save()
        for line_item in services:
            price = line_item.get('amount')
            discount_sum = sum([discount['amount'] for discount in line_item['discount_amounts']])
            line_item = InvoiceLineItem.objects.create(
                price=price,
                discount=discount_sum,
                subscription=created_sub if price >=0 else None,
                invoice=invoice,
                description=line_item.get('description')
            )

    elif invoice and invoice.status == STATUS_PAID:
        # attempt to update already paid invoice
        pass
    elif invoice:  # updating invoice data
        invoice.update_obj(invoice_data)
        invoice.save()


def stripe_subscription_retrieve(subscription_id, expand=()):
    """
    Getting subscription data from Stripe.

    :param expand: request to get additional fields related to the subscription.
    """
    try:
        stripe_subscription = stripe.Subscription.retrieve(subscription_id, expand=expand)
    except Exception as error:
        raise APIException(detail=error, code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return stripe_subscription



@stripe_exception_decorator
def update_stripe_subscription( user, new_plan, coupon=None, redirect_url=None):
    """
        Updates subscription on the Stripe side and immediately processes
        its value received from the service
    """

    user_subscription = user.subscriptions.filter(status__in=[STATUS_PAID, STATUS_PAID_CANCELED, STATUS_PENDING, STATUS_TRIAL]).latest('start_date')
    stripe_subscription = stripe_subscription_retrieve(user_subscription.payment_subscription_id)

    try:
        """ If schedule subscription exists - cancel it """
        if user_subscription.scheduled_plan:
            stripe_logger.info(f'Sending request to release scheduled subscription of {user.email}')
            # self.release_scheduled_subscription(user_payment_service) # TODO
            stripe_logger.info(f'Scheduled subscription of {user.email} released successfully')

        updated_subscription = stripe.Subscription.modify(
            stripe_subscription.id,
            expand=['latest_invoice'],
            # cancel_at_period_end=False,
            payment_behavior='pending_if_incomplete',
            proration_behavior='always_invoice',
            coupon = coupon,
            items=[{
                'id': stripe_subscription['items']['data'][0].id,
                'price': new_plan.payment_plan_id
            }]
        )
        # created_subscription = Subscription(
        #     user=user,
        #     plan=new_plan,
        #     payment_subscription_id=updated_subscription.id,
        #     paid_amount = updated_subscription.latest_invoice.amount_paid,
        #     start_date = datetime.fromtimestamp(updated_subscription.current_period_start, tz=timezone.utc),
        #     next_payment_date = datetime.fromtimestamp(updated_subscription.current_period_end, tz=timezone.utc),
        #     status=get_status(updated_subscription.status)
        # )
        # created_subscription.save()

        # user_subscription.mark_sub_as_canceled_or_expired()
    except stripe_errors.CardError as error:
        raise APIException(detail=error.user_message.split(': ')[0], code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return __handle_stripe_subscriptions_response(user, updated_subscription, None, created=False, redirect_url=redirect_url)




def stripe_schedule_subscription(user, new_plan, coupon=None):
    """Scheduling subscription plan changing"""
    user_subscription = user.subscriptions.filter(status__in=[STATUS_PAID, STATUS_PAID_CANCELED, STATUS_PENDING, STATUS_TRIAL]).latest('start_date')
    stripe_subscription = stripe_subscription_retrieve(user_subscription.payment_subscription_id)

    if stripe_subscription.get('schedule'):
        scheduled_subscription = stripe.SubscriptionSchedule.retrieve(stripe_subscription['schedule'])
    else:
        scheduled_subscription = stripe.SubscriptionSchedule.create(from_subscription=stripe_subscription.id)
    current_phase = {
        "start_date": stripe_subscription['current_period_start'],
        "end_date": stripe_subscription['current_period_end'],
        "items": [
            {
                "price": stripe_subscription['items']['data'][0]['plan']['id'],
            }
        ]
    }

    if new_plan:
        end_behavior = "release"
        phases = [
            current_phase,
            {
                "start_date": stripe_subscription['current_period_end'],
                "coupon": coupon,
                "items": [
                    {
                        "price": new_plan.payment_plan_id
                    }
                ]
            }
        ]
        default_settings = {
            "collection_method": "charge_automatically",
            "billing_cycle_anchor": "phase_start"
        }

    else:
        end_behavior = "cancel"
        phases = [
            current_phase
        ]
        default_settings = None

    data = {
        "end_behavior": end_behavior,
        "phases": phases,
    }
    if default_settings:
        data.update({"default_settings": default_settings})


    scheduled = stripe.SubscriptionSchedule.modify(scheduled_subscription['id'], **data)

    # update inner data
    user_subscription.scheduled_plan = new_plan
    if not new_plan:
        user_subscription.expire_date = user_subscription.next_payment_date
        user_subscription.next_payment_date = None
        user_subscription.status = STATUS_PAID_CANCELED
    user_subscription.save(update_fields=['scheduled_plan', 'expire_date', 'status', 'next_payment_date'])


    return scheduled



@stripe_exception_decorator
def stripe_cancel_scheduled_changes(user):
    user_subscription = user.subscriptions.filter(
        status__in=[STATUS_PAID, STATUS_PAID_CANCELED, STATUS_TRIAL]
    ).latest('start_date')
    stripe_subscription = stripe_subscription_retrieve(user_subscription.payment_subscription_id)
    if not stripe_subscription.schedule:
        raise CustomAPIException(
            detail= {'detail': "Subscription has no scheduled changes."},
            code=status.HTTP_400_BAD_REQUEST)

    stripe.SubscriptionSchedule.modify(
        stripe_subscription.schedule, end_behavior='release'
    )

    stripe.SubscriptionSchedule.release(
        stripe_subscription.schedule
    )
    stripe_subscription = stripe_subscription_retrieve(user_subscription.payment_subscription_id)
    old_schedule = str(user_subscription.scheduled_plan.id) if user_subscription.scheduled_plan else None

    user_subscription.update_obj(
        {
            "status": get_status(stripe_subscription['status']),
            'expire_date': None,
            'next_payment_date': datetime.fromtimestamp(stripe_subscription['current_period_end'], tz=timezone.utc),
            'scheduled_plan': None,
        }
    )
    user_subscription.save()
    return old_schedule


