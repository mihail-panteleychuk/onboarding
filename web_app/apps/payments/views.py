from datetime import datetime

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe.error import InvalidRequestError

from apps.core.exceptions import CustomAPIException
from apps.payments import serializers
from apps.payments.models import BillingAddress, Card, Invoice
from apps.payments.utils import (
    cancel_subscription,
    create_subscription_for_user,
    get_status,
    stripe_cancel_scheduled_changes,
    stripe_logger,
    stripe_schedule_subscription,
    update_stripe_subscription,
    write_invoice,
)
from apps.subscription.constants import PaymentStatus
from apps.subscription.models import Plan, Subscription
from apps.user.models import Country
from apps.user.serializers import FullUserInfoSerializer
from apps.billing.services import BillingService
from apps.billing.stripe_service import StripeService

User = get_user_model()


class CreateCardView(generics.CreateAPIView):
    queryset = Card.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = FullUserInfoSerializer

    def __attach_payment_method(self, payment_id):
        """
        Attach a payment method to the user's Stripe customer account.

        Args:
            payment_id (PaymentMethod): The ID of the payment method to attach.

        Raises:
            CustomAPIException: If attaching the payment method fails.
        """
        payment_user_id = self.request.user.payment_service_user_id
        try:
            stripe.PaymentMethod.attach(payment_id, customer=payment_user_id)
        except InvalidRequestError as e:
            stripe_logger.error(f"LINE:28:: {e}")
            raise CustomAPIException(
                detail={"detail": e.error.message},
                code=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            raise CustomAPIException(detail={"detail": str(e)}, code=status.HTTP_400_BAD_REQUEST)
        try:
            stripe.Customer.modify(
                payment_user_id,
                invoice_settings={"default_payment_method": payment_id},
            )
        except Exception as e:
            stripe_logger.error(f"LINE:37:: {e}")
            raise CustomAPIException(detail={"detail": str(e)}, code=status.HTTP_400_BAD_REQUEST)

    def __create_billing_address(self, card, request_data):
        """
        Create a billing address for the given card.

        Args:
            card (Card): The card associated with the billing address.
            request_data (dict): Data containing information about the billing address.

        Raises:
            CustomAPIException: If creating the billing address fails.
        """
        address = serializers.StripeCardBillingSerializer(
            instance=request_data["payment_method"]["billing_details"]["address"],
            context={"request": self.request},
        )

        BillingAddress.objects.create(
            **address.data,
            card=card,
            first_name=request_data["first_name"],
            last_name=request_data["last_name"],
            country=Country.objects.get(pk=request_data["country"]),
            state=request_data.get("state"),
        )

    def __create_card(self, request_data):
        """
        Create a card for the user based on the provided payment method data.

        Args:
            request_data (dict): Data containing information about the card and payment method.

        Raises:
            CustomAPIException: If creating the card or billing address fails.
        """
        card_data = request_data["payment_method"]["card"]

        card = Card(
            last4=card_data["last4"],
            exp_month=card_data["exp_month"],
            exp_year=card_data["exp_year"],
            brand=card_data["brand"],
            country=Country.objects.filter(country_code=card_data["country"]).first(),
            payment_method_id=request_data["payment_method"]["id"],
            user=self.request.user,
            active=True,
        )
        card.save()
        self.__create_billing_address(card, request_data)

    def post(self, request, *args, **kwargs):
        serializer = serializers.CreateCardViewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.data
        if self.request.user.cards.filter(payment_method_id=data["payment_method"]["id"]).exists():
            return Response(
                {"message": {"detail": "Payment method already exists"}},
                status=status.HTTP_409_CONFLICT,
            )

        self.__attach_payment_method(data["payment_method"]["id"])
        self.__create_card(data)
        resp = self.get_serializer(self.request.user)
        return Response(resp.data, status=status.HTTP_201_CREATED)


class CreateSubscriptionView(CreateCardView):
    queryset = get_user_model().objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = FullUserInfoSerializer

    def post(self, request, *args, **kwargs):
        serializer = serializers.CreateSubscriptionViewSerializer(
            data=request.data,
            context={"request": self.request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.data
        if data.get("payment_method"):
            resp = super().post(request, *args, **kwargs)
            if (
                resp.status_code != status.HTTP_201_CREATED
                and resp.data["message"]["detail"] != "Payment method already exists"
            ):
                return resp
        redirect_url = data.pop("redirect_url", None)
        resp = create_subscription_for_user(
            self.request.user,
            data["plan"],
            coupon=data["discount"],
            redirect_url=redirect_url,
        )
        if not isinstance(resp, tuple):
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)

        created_subscription, redirect_link = resp

        if redirect_link:
            return Response(
                {"paid": False, "link": redirect_link},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        return Response(
            {"user": self.get_serializer(self.request.user).data, "paid": True},
            status=status.HTTP_201_CREATED,
        )


class UpdateSubscriptionView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = FullUserInfoSerializer

    def delete(self, request, *args, **kwargs):
        """
        Cancelling scheduled changes or scheduled cancellation
        """
        old_schedule = stripe_cancel_scheduled_changes(self.request.user)
        if isinstance(old_schedule, (str, type(None))):
            return Response(
                {
                    "user": self.get_serializer(self.request.user).data,
                    "old_schedule": old_schedule,
                },
                status=status.HTTP_200_OK,
            )

    def post(self, request, *args, **kwargs):
        serializer = serializers.UpdateSubscriptionViewSerializer(
            data=request.data,
            context={"request": self.request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.data
        redirect_url = data.pop("redirect_url", None)
        data["plan"] = (
            get_object_or_404(Plan.objects.all(), pk=data["plan"]) if data["plan"] else None
        )
        if data["force"]:
            redirect_link = update_stripe_subscription(
                self.request.user,
                data["plan"],
                coupon=data["discount"],
                redirect_url=redirect_url,
            )
            if redirect_link:
                return Response(
                    {"paid": False, "link": redirect_link},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
        else:
            stripe_schedule_subscription(self.request.user, data["plan"], coupon=data["discount"])

        return Response(
            {"user": self.get_serializer(self.request.user).data, "paid": True},
            status=status.HTTP_201_CREATED,
        )


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Invoice.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.DetailedInvoiceSerializer
    lookup_field = "invoice_id"
    filter_backends = (filters.OrderingFilter,)
    ordering = "-issued"

    def get_serializer_class(self):
        if self.action == "retrieve":
            self.serializer_class = serializers.DetailedInvoiceSerializer
        elif self.action == "list":
            self.serializer_class = serializers.ListInvoiceSerializer

        return super().get_serializer_class()

    def get_queryset(self):
        return self.request.user.invoices.all()


class StripeWebhookView(APIView):
    """
    View that receives all webhook requests belonging to Stripe payment service.

    Due to lack of async ability in django we have to use stripe webhook.
    Stripe webhook sending all events bound
    to payments (invoices, subscriptions, customers, etc) in json.
    This method makes possible to handle 3D-secure payments or subscriptions recurring
    just by usual requests.
    Before using it, make sure webhook is signing correct stripe-signature to prevent
    unexpected requests from other source.
    """

    permission_classes = []

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests to the webhook endpoint.

        This method verifies the signature and processes the webhook event.

        Args:
            request (Request): The incoming request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: HTTP response indicating the webhook event was accepted.
        """
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        # Retrieve the event by verifying the signature using the raw body
        # and secret if webhook signing is configured.
        signature = request.headers.get("stripe-signature")
        event = stripe.Webhook.construct_event(
            payload=request.body,
            sig_header=signature,
            secret=webhook_secret,
        )
        data = event["data"]
        event_type = event["type"]

        if event_type in [
            "invoice.finalized",
            "invoice.payment_succeeded",
            "invoice.paid",
            "invoice.voided",
        ]:
            stripe_subscription = stripe.Subscription.retrieve(
                event["data"]["object"]["subscription"],
            )

            subscription = Subscription.objects.filter(
                payment_subscription_id=stripe_subscription["id"],
                status__in=(
                    PaymentStatus.active_statuses
                    if event_type not in ["invoice.voided", "invoice.payment_failed"]
                    else PaymentStatus.values
                ),
            ).latest("created")

            # write down an invoice
            write_invoice(
                stripe_subscription,
                invoice_source_data=data["object"],
                created_sub=subscription,
            )

        if event_type == "invoice.payment_failed":
            if data["object"]["billing_reason"] == "subscription_create":
                cancel_subscription(stripe_subscription["id"])
            elif data["object"]["billing_reason"] == "subscription_update":
                stripe_subscription = stripe.Subscription.retrieve(
                    event["data"]["object"]["subscription"],
                )
                latest_invoice = stripe_subscription["latest_invoice"]
                if data["object"]["attempt_count"] > 0:
                    stripe.Invoice.void_invoice(latest_invoice)

        if event["type"] == "customer.subscription.updated" and event["data"].get(
            "previous_attributes",
        ):
            # handling scheduled updating
            subscription = event["data"]["object"]
            previous_attributes = event["data"]["previous_attributes"]
            if (
                previous_attributes.get("plan")
                and previous_attributes["plan"]["id"] != subscription["plan"]["id"]
            ):
                user_subscription = get_object_or_404(
                    Subscription.objects.all(),
                    plan__payment_plan_id=previous_attributes["plan"]["id"],
                    user__payment_service_user_id=subscription["customer"],
                )
                expire_date = subscription.get("current_period_start", timezone.now().timestamp())
                expire_date = datetime.fromtimestamp(int(expire_date), tz=timezone.utc)
                user_subscription.update_obj(
                    {
                        "payment_subscription_id": None,
                        "expire_date": expire_date,
                        "next_payment_date": None,
                        "scheduled_plan": None,
                    },
                )
                user_subscription.save()
                user_subscription.update_obj(
                    {
                        "pk": None,
                        "payment_subscription_id": subscription["id"],
                        "start_date": datetime.fromtimestamp(
                            subscription["current_period_start"],
                            tz=timezone.utc,
                        ),
                        "next_payment_date": datetime.fromtimestamp(
                            subscription["current_period_end"],
                            tz=timezone.utc,
                        ),
                        "expire_date": None,
                        "status": get_status(subscription["status"]),
                        "plan": Plan.objects.get(payment_plan_id=subscription["plan"]["id"]),
                        "scheduled_plan": None,
                    },
                )
                user_subscription.save()
            elif previous_attributes.get("status"):
                user_subscription = get_object_or_404(
                    Subscription.objects.all(),
                    plan__payment_plan_id=subscription["plan"]["id"],
                    user__payment_service_user_id=subscription["customer"],
                    status=get_status(previous_attributes.get("status")),
                )
                user_subscription.update_obj({"status": get_status(subscription["status"])})
                user_subscription.save()

        if event["type"] == "subscription_schedule.canceled":
            subscription = event["data"]["object"]
            user_subscription = get_object_or_404(
                Subscription.objects.all(),
                payment_subscription_id=subscription["subscription"],
                user__payment_service_user_id=subscription["customer"],
                status=PaymentStatus.PAID_CANCELED,
            )
            user_subscription.update_obj(
                {
                    "status": get_status(subscription["status"]),
                    "expire_date": datetime.fromtimestamp(
                        subscription.get("canceled_at", int(timezone.now().timestamp())),
                        tz=timezone.utc,
                    ),
                },
            )
            user_subscription.save()

        # Handle balance top-up via Checkout Session
        if event_type == "checkout.session.completed":
            session = data["object"]
            metadata = session.get("metadata", {})
            
            # Check if this is a balance top-up
            if metadata.get("type") == "balance_topup":
                from decimal import Decimal
                from django.contrib.auth import get_user_model
                
                User = get_user_model()
                user_id = metadata.get("user_id")
                amount_str = metadata.get("amount")
                
                if user_id and amount_str:
                    try:
                        user = User.objects.get(id=user_id)
                        amount = Decimal(amount_str)
                        
                        # Create top-up transaction
                        BillingService.create_topup_transaction(
                            user=user,
                            amount=amount,
                            external_id=session.get("id"),
                        )
                        stripe_logger.info(
                            f"Balance top-up completed for user {user_id}: ${amount}"
                        )
                    except User.DoesNotExist:
                        stripe_logger.error(f"User {user_id} not found for balance top-up")
                    
                    except Exception as e:
                        stripe_logger.error(
                            f"Failed to process balance top-up for user {user_id}: {str(e)}"
                        )

        return Response({"accepted": True})  # returning response only to prevent issues
