"""Business logic services for billing operations."""

from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction as db_transaction
from rest_framework.exceptions import ValidationError

from apps.billing.constants import ServiceStatus, TransactionDirection, TransactionKind
from apps.billing.models import BalanceTransaction, ServiceRequest, ServiceType


class BillingService:
    """Service for billing operations: balance, service requests, transactions."""

    @staticmethod
    def get_user_balance(user) -> Decimal:
        """Get current balance for a user."""
        return BalanceTransaction.objects.calculate_user_balance(user)


    @staticmethod
    def check_sufficient_balance(user, required_amount: Decimal) -> bool:
        """Check if user has sufficient balance."""
        current_balance = BillingService.get_user_balance(user)
        return current_balance >= required_amount

    
    @staticmethod
    @db_transaction.atomic
    def create_service_request(user, service_type: ServiceType) -> ServiceRequest:
        """Create a service request with balance check and fund reservation.

        This method:
        1. Checks if user has sufficient balance.
        2. Creates ServiceRequest with PENDING status.
        3. Reserves funds from user balance.
        4. Returns the created request.        
        """
        if not service_type.is_active:
            raise ValidationError(
                {"service_type": "Service type is not available for new requests."}
            )

        if not BillingService.check_sufficient_balance(user, service_type.price_usd):
            raise ValidationError(
                {
                    "balance": f"Insufficient balance. Required: {service_type.price_usd} USD, "
                    f"available: {BillingService.get_user_balance(user)} USD."
                }
            )

        service_request = ServiceRequest.objects.create(
            user=user,
            service_type=service_type,
            status=ServiceStatus.PENDING,
        )

        service_request.reserve_funds()

        return service_request

    
    @staticmethod
    @db_transaction.atomic
    def cancel_service_request_by_user(
        user,
        service_request: ServiceRequest,
    ) -> Optional[BalanceTransaction]:
        """Cancel a service request by user.
        User can only cancel requests with PENDING status.        
        """

        if service_request.user != user:
            raise ValidationError({"detail": "You can only cancel your own requests."})

        if not service_request.can_be_cancelled_by_user():
            raise ValidationError(
                {"detail": "Only pending requests can be cancelled by user."}
            )

        return service_request.cancel()

    
    @staticmethod
    @db_transaction.atomic
    def create_topup_transaction(
        user,
        amount: Decimal,
        external_id: Optional[str] = None,
    ) -> BalanceTransaction:
        """Create a top-up transaction (balance increase)."""
        if amount <= Decimal("0"):
            raise ValidationError({"amount": "Top-up amount must be positive."})

        # Check if transaction with this external_id already exists (idempotency)
        if external_id:
            existing = BalanceTransaction.objects.filter(
                user=user,
                kind=TransactionKind.TOPUP,
                external_id=external_id,
            ).first()
            if existing:
                return existing

        return BalanceTransaction.objects.create(
            user=user,
            direction=TransactionDirection.IN,
            kind=TransactionKind.TOPUP,
            amount=amount,
            external_id=external_id,
        )
