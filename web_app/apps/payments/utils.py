import json
import logging
import traceback
from datetime import datetime

import stripe
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from stripe import error as stripe_errors

from apps.admin_panel.models import Settings
from apps.core.exceptions import APIException, CustomAPIException
from apps.payments.models import Invoice, InvoiceLineItem, Subscription
from apps.subscription.constants import PaymentStatus
from apps.subscription.models import Plan

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe_logger = logging.getLogger("stripe")


def stripe_exception_decorator(func):
    """
    Decorator for handling Stripe and custom payment service errors.

    Args:
        func (callable): The function to be decorated.

    Returns:
        callable: The decorated function.
    """

    def inner_function(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except stripe_errors.CardError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = "CardError occurred"
            resp = {"detail": e_m}
        except stripe_errors.APIError as e:
            e_m = e
            trace = traceback.format_exc()
            message = "Operation failed"
            resp = {"detail": "Operation cannot be processed"}
        except stripe_errors.InvalidRequestError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = "Invalid request"
            resp = {"detail": e_m}
        except (stripe_errors.AuthenticationError, stripe_errors.PermissionError) as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = "Auth error occurred"
            resp = {"detail": e_m}
        except stripe_errors.RateLimitError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = "RateLimitError error occurred"
            resp = {"detail": e_m}
        except stripe_errors.StripeError as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = "Stripe general error"
            resp = {"detail": e_m}
        except CustomAPIException as e:
            e_m = str(e.detail)
            trace = traceback.format_exc()
            message = "APIException handling"
            resp = e
        except APIException as e:
            e = CustomAPIException(detail=e.detail, code=e.status_code)
            e_m = str(e.detail)
            trace = traceback.format_exc()
            message = "APIException handling"
            resp = e
        except Exception as e:
            e_m = str(e)
            trace = traceback.format_exc()
            message = "Unexpected exception"
            resp = {"detail": _("Something went wrong due processing your data!")}

        args = str(args)
        kwargs = str(kwargs)
        stripe_logger.error(
            json.dumps(
                {
                    "timestamp": str(datetime.now()),
                    "message": message,
                    "error": e_m,
                    "traceback": trace,
                    "args": args,
                    "kwargs": kwargs,
                },
            ),
        )
        if isinstance(resp, dict) and "detail" in resp.keys():
            raise CustomAPIException(detail=resp, code=status.HTTP_400_BAD_REQUEST)
        else:
            raise resp

    return inner_function


def retrieve_coupon(coupon_id):
    """
    Retrieve a coupon by its ID.

    Docs: https://stripe.com/docs/api/coupons/retrieve?lang=python
    ! add usage os this func!!

    Args:
        coupon_id (str): The ID of the coupon to retrieve.

    Returns:
        dict: A dictionary representing the retrieved coupon.
    """
    result = stripe.Coupon.retrieve(coupon_id)
    return result.coupon


@stripe_exception_decorator
def create_coupon(coupon):
    """
    Create a coupon in the Stripe dashboard.

    Args:
        coupon (str): The ID of the coupon to create.

    Returns:
        dict: A dictionary representing the created coupon.
    """
    try:
        discount = Settings.objects.get("discount").get_value()
    except:  # noqa: E722
        discount = 10.0
    result = stripe.Coupon.create(
        {
            "id": coupon,
            "name": f"Refershion {coupon}",
            "percent_off": discount,
            "duration": "forever",
        },
    )

    return stripe.util.convert_to_dict(result)


@stripe_exception_decorator
def retrieve_stripe_account_billing():
    """
    Retrieve billing information from the connected Stripe account.

    Stripe is returning data about bussiness profile only in `Live Mode`.
    So for development environment - data is hardcoded

    Returns:
        dict: A dictionary containing the billing information.
    """
    if settings.IS_PRODUCTION:
        data = stripe.Account.retrieve(settings.STRIPE_ACCOUNT_ID)
        return data["business_profile"]
    else:
        return settings.TEST_BUSSINESS_PROFILE


def get_status(status):
    """
    Map Stripe statuses to custom status models (see: subscription.constants).

    Args:
        status (str): The status from Stripe.

    Returns:
        str: The corresponding custom status.
    """
    statuses_mapping = {
        "paid": PaymentStatus.PAID,
        "active": PaymentStatus.PAID,
        "trialing": PaymentStatus.TRIAL,
        "canceled": PaymentStatus.CANCELED,
        "unpaid": PaymentStatus.FAILED,
        "incomplete_expired": PaymentStatus.FAILED,
        "incomplete": PaymentStatus.PENDING,
        "past_due": PaymentStatus.PENDING,
        # invoice statuses
        "draft": "",  # ! invoice
        "open": PaymentStatus.PENDING,
        "void": PaymentStatus.FAILED,
    }
    return statuses_mapping.get(status, PaymentStatus.FAILED)


# =======================================================================================
# =======================================================================================
# =========================== STRIPE CUSTOMER PROCESSING ================================
# =======================================================================================
# =======================================================================================
@stripe_exception_decorator
def create_stripe_customer(user):
    """
    Create customer account on Chargebee for a new user and save its customer_id.

    Args:
        user (user.User): User model object.
    """
    if not user.payment_service_user_id:
        result = stripe.Customer.create(
            email=user.email,
            name=user.full_name,
            metadata={"ID": user.id},
        )
        user.payment_service_user_id = result.id
        user.save()


@stripe_exception_decorator
def cancel_all_user_subscriptions(customer_id):
    """
    Cancel all active subscriptions for a given customer.

    Args:
        customer_id (str): The ID of the customer whose subscriptions should be canceled.
    """
    subscriptions = stripe.Subscription.list(customer=customer_id, status="active", limit=100)

    for subscription in subscriptions:
        stripe.Subscription.delete(
            subscription["id"],
        )


def cancel_subscription(subscription_id):
    """
    Cancel a subscription.

    Args:
        subscription_id (str): The ID of the subscription to be canceled.
    """
    stripe.Subscription.delete(subscription_id)


@stripe_exception_decorator
def retrieve_customer(user):
    """
    Retrieve customer information from Stripe.

    Args:
        user (User): The user object whose payment service user ID is used to retrieve the customer.

    Returns:
        dict: The retrieved customer information.
    """
    customer = stripe.Customer.retrieve(user.payment_service_user_id)
    return customer


@stripe_exception_decorator
def remove_customer(customer_id):
    """
    Remove a customer from Stripe.

    Args:
        customer_id (str): The ID of the customer to be removed.

    Returns:
        bool: True if the customer is successfully deleted, False otherwise.
    """
    result = stripe.Customer.delete(customer_id)
    return result.deleted


@stripe_exception_decorator
def sync_user_data(user):
    """
    Synchronize user data with Stripe.

    Args:
        user (User): The user object whose data will be synchronized with Stripe.

    Raises:
        CustomAPIException: If an error occurs during the synchronization process.

    Note:
        This function modifies the user's data in the Stripe customer record. It updates the email, full name,
           phone number, and preferred locales.
    """
    if user.payment_service_user_id:
        if user.phone_code and user.phone_code.code and user.phone:
            phone_number = f"{user.phone_code.code}{user.phone}"
        else:
            phone_number = None

        stripe.Customer.modify(
            user.payment_service_user_id,
            email=user.email,
            name=user.full_name,
            phone=phone_number,
            preferred_locales=[
                user.language,
            ],
        )


@stripe_exception_decorator
def update_customer_billing_info(billing_object, _type="billing"):
    """
    Update user billing information on Stripe.

    Args:
        billing_object (BillingAddress): The updated billing address object containing the new billing information.

        _type (str, optional): The type of billing information to update. Defaults to "billing".

    Raises:
        CustomAPIException: If an error occurs during the billing information update process.

    Note:
        This function modifies the user's billing information in the Stripe customer record. It updates the address,
            including city, country, address lines, postal code, and state.

    """
    if _type == "billing":
        stripe.Customer.modify(
            billing_object.card.user.payment_service_user_id,
            address={
                "city": billing_object.city,
                "country": billing_object.country.country_code,
                "line1": billing_object.address_line_1,
                "line2": billing_object.address_line_2,
                "postal_code": billing_object.postal_code,
                "state": billing_object.state,
            },
        )


# =======================================================================================
# =========================== STRIPE SUBSCRIPTIONS PROCESSING ===========================
# =======================================================================================


def __handle_stripe_subscriptions_response(
    user,
    stripe_response,
    created_sub=None,
    created=True,
    redirect_url=None,
):
    """
    Handle Stripe subscription response.

    This function processes the response received from Stripe after creating or updating a subscription.
    It handles scenarios like pending payments, incomplete payments, and past-due invoices.

    Args:
        user (User): The user associated with the subscription.
        stripe_response (dict): The response received from Stripe.
        created_sub (Subscription, optional): The created subscription object. Defaults to None.
        created (bool, optional): Indicates whether the subscription was created or updated. Defaults to True.
        redirect_url (str, optional): The URL to redirect the user to. Defaults to None.

    Returns:
        str: The payment required link if additional payment is needed.

    Raises:
        CustomAPIException: If an unexpected error occurs during the response handling process.

    """
    if created_sub:
        write_invoice(stripe_response, stripe_response["latest_invoice"], created_sub)

    if stripe_response["status"] in ["past_due", "incomplete"] or stripe_response.get(
        "pending_update",
    ):
        invoice = stripe.Invoice.retrieve(stripe_response["latest_invoice"]["id"])
        if invoice["status"] == "open":
            payment_intent = stripe.PaymentIntent.retrieve(invoice["payment_intent"])
            if payment_intent.get("next_action"):
                try:
                    success_url = redirect_url or settings.STRIPE_ORDER_SUCCESS_URL
                    intent = stripe.PaymentIntent.confirm(
                        invoice["payment_intent"],
                        payment_method=payment_intent["payment_method"],
                        return_url=success_url + payment_intent["client_secret"],
                    )

                    payment_required_link = intent["next_action"]["redirect_to_url"]["url"]
                    return payment_required_link
                except Exception as error:
                    raise CustomAPIException(
                        detail={"detail": error},
                        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
        # this error will occur only if stripe will change something in their api
        raise CustomAPIException(
            detail={"detail": "Got an unexpected error"},
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def __user_sub_already_exists(user):
    """
    Check if the user already has an active subscription.

    Args:
        user (User): The user object.

    Returns:
        bool: True if the user already has an active subscription, False otherwise.
    """
    subscriptions = stripe.Subscription.list(
        customer=user.payment_service_user_id,
        status="active",
        limit=100,
    )
    return len(subscriptions["data"]) > 0


@stripe_exception_decorator
def create_subscription_for_user(user, plan_id, coupon=None, redirect_url=None):
    """
    Initial subscription creation from onboarding/checkout.

    Args:
        user (user.User): User object who is subscribing.
        plan_id (str): Identifier of the selected plan for subscription.
        coupon (str, optional): Discount code if coupon is applied. Defaults to None.
        redirect_url (str, optional): Redirect URL. Defaults to None.

    Returns:
        tuple: A tuple containing the created subscription object and the redirect link.
            The redirect link is provided if a payment action is required, otherwise None.
    """
    if __user_sub_already_exists(user):
        raise CustomAPIException(
            detail={"detail": "User already has a subscription."},
            code=status.HTTP_409_CONFLICT,
        )

    try:
        plan = Plan.objects.get(pk=plan_id)
    except:  # noqa: E722
        return {"message": {"detail": "No plan found"}}

    stripe_subscription = stripe.Subscription.create(
        customer=user.payment_service_user_id,
        items=[{"price": plan.payment_plan_id}],
        coupon=coupon,
        expand=["latest_invoice"],
        payment_behavior="allow_incomplete",
    )

    created_subscription = Subscription(
        user=user,
        plan=plan,
        payment_subscription_id=stripe_subscription.id,
        paid_amount=stripe_subscription.latest_invoice.amount_paid,
        start_date=datetime.fromtimestamp(
            stripe_subscription.current_period_start,
            tz=timezone.utc,
        ),
        next_payment_date=datetime.fromtimestamp(
            stripe_subscription.current_period_end,
            tz=timezone.utc,
        ),
        status=get_status(stripe_subscription.status),
    )
    created_subscription.save()

    if not created_subscription:
        return {"message": {"detail": "Subscription creating failed."}}

    redirect_link = __handle_stripe_subscriptions_response(
        user,
        stripe_subscription,
        created_subscription,
        redirect_url=redirect_url,
    )

    return created_subscription, redirect_link


def write_invoice(stripe_subscription, invoice_source_data, created_sub):
    """
    Write invoice data to the database based on payment service information.

    Args:
        stripe_subscription (dict): Stripe subscription data.
        invoice_data (dict): Invoice data received from the payment service.
        created_subscription (Subscription): The created subscription object.
    """
    invoice_number = invoice_source_data["number"]
    invoice_status = get_status(invoice_source_data["status"])

    services = invoice_source_data["lines"]["data"]

    invoice_data = {
        "status": invoice_status,
        "user": created_sub.user,
        "total": invoice_source_data["total"],
        "issued_date": now().date(),
        "issued": now(),
        "card": created_sub.user.cards.filter(active=True).latest("created"),
    }

    invoice = Invoice.objects.filter(invoice_id=invoice_number).first()
    if not invoice and invoice_number:
        invoice = Invoice.objects.create(invoice_id=invoice_number, **invoice_data)
        invoice.save()
        for line_item in services:
            price = line_item.get("amount")
            discount_sum = sum([discount["amount"] for discount in line_item["discount_amounts"]])
            line_item = InvoiceLineItem.objects.create(
                price=price,
                discount=discount_sum,
                subscription=created_sub if price >= 0 else None,
                invoice=invoice,
                description=line_item.get("description"),
            )

    elif invoice and invoice.status == PaymentStatus.PAID:
        # attempt to update already paid invoice
        pass
    elif invoice:  # updating invoice data
        invoice.update_obj(invoice_data)
        invoice.save()


def stripe_subscription_retrieve(subscription_id, expand=()):
    """
    Retrieve subscription data from Stripe.

    Args:
        subscription_id (str): The ID of the subscription to retrieve.
        expand (tuple, optional): Additional fields to expand related to the subscription.

    Returns:
        dict: Subscription data retrieved from Stripe.

    Raises:
        APIException: If an error occurs during the retrieval process.
    """
    try:
        stripe_subscription = stripe.Subscription.retrieve(subscription_id, expand=expand)
    except Exception as error:
        raise APIException(detail=error, code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return stripe_subscription


@stripe_exception_decorator
def update_stripe_subscription(user, new_plan, coupon=None, redirect_url=None):
    """
    Updates subscription on the Stripe side and processes its value immediately.

    Args:
        user (User): The user whose subscription is being updated.
        new_plan (Plan): The new plan for the subscription.
        coupon (str, optional): The coupon code to apply to the subscription.
        redirect_url (str, optional): The URL to redirect to after updating the subscription.

    Returns:
        dict: Updated subscription data from Stripe.

    Raises:
        CustomAPIException: If an error occurs during the update process.
    """

    user_subscription = user.subscriptions.filter(
        status__in=[
            PaymentStatus.PAID,
            PaymentStatus.PAID_CANCELED,
            PaymentStatus.PENDING,
            PaymentStatus.TRIAL,
        ],
    ).latest("start_date")
    stripe_subscription = stripe_subscription_retrieve(user_subscription.payment_subscription_id)

    try:
        """If schedule subscription exists - cancel it"""
        if user_subscription.scheduled_plan:
            stripe_logger.info(
                f"Sending request to release scheduled subscription of {user.email}",
            )
            # self.release_scheduled_subscription(user_payment_service) # TODO
            stripe_logger.info(f"Scheduled subscription of {user.email} released successfully")

        updated_subscription = stripe.Subscription.modify(
            stripe_subscription.id,
            expand=["latest_invoice"],
            payment_behavior="pending_if_incomplete",
            proration_behavior="always_invoice",
            coupon=coupon,
            items=[
                {
                    "id": stripe_subscription["items"]["data"][0].id,
                    "price": new_plan.payment_plan_id,
                },
            ],
        )

    except stripe_errors.CardError as error:
        raise APIException(
            detail=error.user_message.split(": ")[0],
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return __handle_stripe_subscriptions_response(
        user,
        updated_subscription,
        None,
        created=False,
        redirect_url=redirect_url,
    )


def stripe_schedule_subscription(user, new_plan, coupon=None):
    """
    Schedule a subscription plan change on the Stripe platform.

    Args:
        user (User): The user for whom the subscription plan change is being scheduled.
        new_plan (Plan): The new subscription plan to be scheduled.
        coupon (str, optional): The coupon code to apply to the subscription. Defaults to None.

    Returns:
        dict: The updated subscription schedule data from the Stripe API.

    Raises:
        APIException: If an error occurs while communicating with the Stripe API.

    """
    user_subscription = user.subscriptions.filter(
        status__in=[
            PaymentStatus.PAID,
            PaymentStatus.PAID_CANCELED,
            PaymentStatus.PENDING,
            PaymentStatus.TRIAL,
        ],
    ).latest("start_date")
    stripe_subscription = stripe_subscription_retrieve(user_subscription.payment_subscription_id)

    if stripe_subscription.get("schedule"):
        scheduled_subscription = stripe.SubscriptionSchedule.retrieve(
            stripe_subscription["schedule"],
        )
    else:
        scheduled_subscription = stripe.SubscriptionSchedule.create(
            from_subscription=stripe_subscription.id,
        )
    current_phase = {
        "start_date": stripe_subscription["current_period_start"],
        "end_date": stripe_subscription["current_period_end"],
        "items": [
            {
                "price": stripe_subscription["items"]["data"][0]["plan"]["id"],
            },
        ],
    }

    if new_plan:
        end_behavior = "release"
        phases = [
            current_phase,
            {
                "start_date": stripe_subscription["current_period_end"],
                "coupon": coupon,
                "items": [{"price": new_plan.payment_plan_id}],
            },
        ]
        default_settings = {
            "collection_method": "charge_automatically",
            "billing_cycle_anchor": "phase_start",
        }

    else:
        end_behavior = "cancel"
        phases = [current_phase]
        default_settings = None

    data = {
        "end_behavior": end_behavior,
        "phases": phases,
    }
    if default_settings:
        data.update({"default_settings": default_settings})

    scheduled = stripe.SubscriptionSchedule.modify(scheduled_subscription["id"], **data)

    # update inner data
    user_subscription.scheduled_plan = new_plan
    if not new_plan:
        user_subscription.expire_date = user_subscription.next_payment_date
        user_subscription.next_payment_date = None
        user_subscription.status = PaymentStatus.PAID_CANCELED
    user_subscription.save(
        update_fields=["scheduled_plan", "expire_date", "status", "next_payment_date"],
    )

    return scheduled


@stripe_exception_decorator
def stripe_cancel_scheduled_changes(user):
    """
    Cancel scheduled changes for a user's subscription on the Stripe platform.

    Args:
        user (User): The user whose scheduled changes are being canceled.

    Returns:
        str: The ID of the canceled scheduled plan.

    Raises:
        CustomAPIException: If the subscription has no scheduled changes.
        APIException: If an error occurs while communicating with the Stripe API.
    """
    user_subscription = user.subscriptions.filter(
        status__in=[PaymentStatus.PAID, PaymentStatus.PAID_CANCELED, PaymentStatus.TRIAL],
    ).latest("start_date")
    stripe_subscription = stripe_subscription_retrieve(user_subscription.payment_subscription_id)
    if not stripe_subscription.schedule:
        raise CustomAPIException(
            detail={"detail": "Subscription has no scheduled changes."},
            code=status.HTTP_400_BAD_REQUEST,
        )

    stripe.SubscriptionSchedule.modify(stripe_subscription.schedule, end_behavior="release")

    stripe.SubscriptionSchedule.release(stripe_subscription.schedule)
    stripe_subscription = stripe_subscription_retrieve(user_subscription.payment_subscription_id)
    old_schedule = (
        str(user_subscription.scheduled_plan.id) if user_subscription.scheduled_plan else None
    )

    user_subscription.update_obj(
        {
            "status": get_status(stripe_subscription["status"]),
            "expire_date": None,
            "next_payment_date": datetime.fromtimestamp(
                stripe_subscription["current_period_end"],
                tz=timezone.utc,
            ),
            "scheduled_plan": None,
        },
    )
    user_subscription.save()
    return old_schedule
