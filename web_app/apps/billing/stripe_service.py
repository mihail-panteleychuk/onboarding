"""Stripe integration for billing operations."""

import logging
from decimal import Decimal
from typing import Optional

import stripe
from django.conf import settings
from rest_framework import status

from apps.core.exceptions import CustomAPIException
from apps.payments.utils import create_stripe_customer, stripe_exception_decorator

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe_logger = logging.getLogger("stripe")


@stripe_exception_decorator
def create_checkout_session_for_topup(
    user,
    amount: Decimal,
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
) -> dict:
    """Create a Stripe Checkout Session for balance top-up."""

    if amount <= Decimal("0"):
        raise CustomAPIException(
            detail={"amount": "Top-up amount must be positive."},
            code=status.HTTP_400_BAD_REQUEST,
        )

    # Ensure user has a Stripe customer
    if not user.payment_service_user_id:
        create_stripe_customer(user)

    # Convert Decimal to cents (Stripe uses smallest currency unit)
    amount_cents = int(amount * 100)

    # Default URLs
    if not success_url:
        # Ensure URL has protocol
        front_domain = settings.FRONT_DOMAIN
        
        if not front_domain.startswith(("http://", "https://")):
            front_domain = f"http://{front_domain}"
        
        success_url = f"{front_domain}/billing/topup/success?session_id={{CHECKOUT_SESSION_ID}}"
    
    if not cancel_url:
        # Ensure URL has protocol
        front_domain = settings.FRONT_DOMAIN
    
        if not front_domain.startswith(("http://", "https://")):
            front_domain = f"http://{front_domain}"
    
        cancel_url = f"{front_domain}/billing/topup/cancel"

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=user.payment_service_user_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Balance Top-up",
                            "description": f"Top-up internal balance by ${amount:.2f}",
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": str(user.id),
                "type": "balance_topup",
                "amount": str(amount),
            },
        )

        return {
            "url": checkout_session.url,
            "session_id": checkout_session.id,
        }

    except Exception as e:
        stripe_logger.error(f"Failed to create checkout session for user {user.id}: {str(e)}")
        raise


@stripe_exception_decorator
def retrieve_checkout_session(session_id: str) -> dict:
    """Retrieve a Stripe Checkout Session by ID."""
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return session
    
    except Exception as e:
        stripe_logger.error(f"Failed to retrieve checkout session {session_id}: {str(e)}")
        raise
