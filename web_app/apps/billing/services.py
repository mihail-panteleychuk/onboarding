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
        1. Checks if user has sufficient balance (with row-level locking to prevent race conditions).
        2. Creates ServiceRequest with PENDING status.
        3. Reserves funds from user balance.
        4. Returns the created request.
        
        Uses select_for_update() to lock user's transactions during balance check
        to prevent race conditions when multiple requests are created simultaneously.
        """
        if not service_type.is_active:
            raise ValidationError(
                {"service_type": "Service type is not available for new requests."}
            )

        # Lock user's transactions to prevent race conditions
        # This ensures that balance check and reservation happen atomically
        locked_transactions = BalanceTransaction.objects.for_user(user).select_for_update()
        current_balance = locked_transactions.calculate_balance()
        
        if current_balance < service_type.price_usd:
            raise ValidationError(
                {
                    "balance": f"Insufficient balance. Required: {service_type.price_usd} USD, "
                    f"available: {current_balance} USD."
                }
            )

        service_request = ServiceRequest.objects.create(
            user=user,
            service_type=service_type,
            status=ServiceStatus.PENDING,
        )

        service_request.reserve_funds()

        # Schedule Celery task for auto-confirmation after timeout
        from apps.billing.tasks import auto_confirm_service_request
        
        timeout_seconds = getattr(settings, "BILLING_AUTO_CONFIRM_TIMEOUT", 120)  # Default: 2 minutes
        
        auto_confirm_service_request.apply_async(
            args=[str(service_request.id)],
            countdown=timeout_seconds,
        )
        
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
    def cancel_service_request(
        user,
        service_request: ServiceRequest,
    ) -> Optional[BalanceTransaction]:
        """Cancel a service request (handles both user and admin cases).        
        - User can only cancel pending requests.
        - Admin can cancel any request.
        """
        from apps.user.models import User
        
        # Admin can cancel any request using status change
        if user.role == User.UserRoleChoices.ADMIN:
            BillingService.change_service_request_status(
                service_request=service_request,
                new_status=ServiceStatus.CANCELLED.value,
            )            
            return None
        
        # User can only cancel pending requests
        return BillingService.cancel_service_request_by_user(
            user=user,
            service_request=service_request,
        )

    
    @staticmethod
    @db_transaction.atomic
    def change_service_request_status(
        service_request: ServiceRequest,
        new_status: str,
    ) -> ServiceRequest:
        """Change service request status (admin only).
        
        Valid status transitions:
        - pending → confirmed, cancelled
        - confirmed → in_progress, cancelled
        - in_progress → completed, cancelled
        - completed → (no transitions allowed)
        - cancelled → (no transitions allowed)
        
        When status changes to confirmed, reserved funds are captured (final charge).
        When status changes to cancelled, reserved funds are refunded.
        """
        old_status = service_request.status
        new_status_enum = ServiceStatus(new_status)
        
        # Validate status transition
        valid_transitions = {
            ServiceStatus.PENDING: [ServiceStatus.CONFIRMED, ServiceStatus.CANCELLED],
            ServiceStatus.CONFIRMED: [ServiceStatus.IN_PROGRESS, ServiceStatus.CANCELLED],
            ServiceStatus.IN_PROGRESS: [ServiceStatus.COMPLETED, ServiceStatus.CANCELLED],
            ServiceStatus.COMPLETED: [],  # No transitions from completed
            ServiceStatus.CANCELLED: [],   # No transitions from cancelled
        }
        
        if new_status_enum not in valid_transitions.get(old_status, []):
            raise ValidationError(
                {
                    "status": f"Cannot change status from {old_status} to {new_status}. "
                    f"Valid transitions: {[s.value for s in valid_transitions.get(old_status, [])]}"
                }
            )
        
        # Handle status change logic
        if new_status_enum == ServiceStatus.CANCELLED:
            # Refund reserved funds if any
            service_request.refund_reserved_funds()
        
        elif new_status_enum == ServiceStatus.CONFIRMED and old_status == ServiceStatus.PENDING:
            # Create CAPTURE transaction (final charge) for history
            # Note: RESERVE already decreased balance, CAPTURE is for history only
            BalanceTransaction.objects.create(
                user=service_request.user,
                direction=TransactionDirection.OUT,
                kind=TransactionKind.CAPTURE,
                amount=service_request.reserved_amount,
                service_request=service_request,
            )
        
        service_request.status = new_status_enum
        service_request.save(update_fields=["status"])
        
        return service_request

    
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
