"""Business logic services for billing operations."""

from decimal import Decimal
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.db import transaction as db_transaction
from rest_framework.exceptions import ValidationError

from apps.billing.constants import ServiceStatus, TransactionDirection, TransactionKind
from apps.billing.models import BalanceTransaction, ServiceRequest, ServiceType
from apps.user.models import User


class BillingService:
    """Service for billing operations: balance, service requests, transactions."""

    @staticmethod
    def get_user_balance(user: User) -> Decimal:
        """Get current balance for a user."""
        return BalanceTransaction.objects.calculate_user_balance(user)


    @staticmethod
    def build_user_balance_list(users: Iterable[User]) -> List[dict]:
        """Build list of user balances for admin views.

        Returns a list of dictionaries compatible with existing
        `UserBalanceSerializer` / `UserBalanceListSerializer` structure.
        """
        user_balances: List[dict] = []

        for user in users:
            balance = BillingService.get_user_balance(user)
            user_balances.append(
                {
                    "user_id": user.id,
                    "user_email": user.email,
                    "user_first_name": user.first_name,
                    "user_last_name": user.last_name,
                    "balance": balance,
                }
            )

        return user_balances


    @staticmethod
    def prepare_transactions_export(
        target_user: User,
        ordering_param: Optional[str],
        fields_param: Optional[str],
    ) -> Tuple[Iterable[BalanceTransaction], List[str], Dict[str, Callable[[BalanceTransaction], str]]]:
        """Prepare queryset, fields and field mapping for transactions CSV export.
        """
        # Base queryset
        transactions = BalanceTransaction.objects.for_user(target_user).select_related(
            "user", "service_request"
        )

        # Apply ordering with validation
        ordering_value = ordering_param.strip() if ordering_param else "-created"

        if ordering_value:
            allowed_ordering_fields = {
                "id",
                "user_id",
                "amount",
                "direction",
                "kind",
                "service_request_id",
                "external_id",
                "created",
                "updated",
            }

            is_desc = ordering_value.startswith("-")
            field_name = ordering_value[1:] if is_desc else ordering_value

            if not field_name or field_name not in allowed_ordering_fields:
                allowed_str = ", ".join(sorted(allowed_ordering_fields))
                raise ValueError(
                    f"Invalid ordering field: '{ordering_value}'. Allowed fields: {allowed_str}."
                )

            ordering = f"-{field_name}" if is_desc else field_name
            transactions = transactions.order_by(ordering)

        # Available fields mapping
        available_fields: Dict[str, Callable[[BalanceTransaction], str]] = {
            "id": lambda t: str(t.id),
            "user_id": lambda t: str(t.user.id),
            "user_email": lambda t: t.user.email,
            "direction": lambda t: t.direction,
            "kind": lambda t: t.kind,
            "amount": lambda t: str(t.amount),
            "service_request_id": lambda t: str(t.service_request.id) if t.service_request else "",
            "external_id": lambda t: t.external_id or "",
            "created": lambda t: t.created.strftime("%Y-%m-%d %H:%M:%S") if t.created else "",
            "updated": lambda t: t.updated.strftime("%Y-%m-%d %H:%M:%S") if t.updated else "",
        }

        # Determine fields to export
        fields_value = (fields_param or "").strip()

        if fields_value:
            requested_fields = [f.strip() for f in fields_value.split(",") if f.strip()]
            valid_fields = [f for f in requested_fields if f in available_fields]

            if not valid_fields:
                raise ValueError("No valid fields specified.")

            export_fields = valid_fields
        
        else:
            export_fields = [
                "id",
                "user_email",
                "direction",
                "kind",
                "amount",
                "service_request_id",
                "created",
            ]

        return transactions, export_fields, available_fields

    
    @staticmethod
    def prepare_service_requests_export(
        queryset: Iterable[ServiceRequest],
        fields_param: Optional[str],
    ) -> Tuple[List[str], Iterable[List[str]]]:
        """Prepare data for service requests CSV export.        
        """
        allowed_fields = {
            "id",
            "user_id",
            "user_email",
            "user_first_name",
            "user_last_name",
            "service_type_id",
            "service_type_name",
            "service_type_price_usd",
            "status",
            "reserved_amount",
            "created",
            "updated",
        }

        default_fields: List[str] = [
            "id",
            "user_email",
            "service_type_name",
            "service_type_price_usd",
            "status",
            "reserved_amount",
            "created",
        ]

        if fields_param:
            requested_fields = [f.strip() for f in fields_param.split(",") if f.strip()]
        
        else:
            requested_fields = default_fields

        invalid_fields = [f for f in requested_fields if f not in allowed_fields]

        if invalid_fields:
            allowed_str = ", ".join(sorted(allowed_fields))
            invalid_str = ", ".join(invalid_fields)
            raise ValueError(
                "Invalid fields: "
                + invalid_str
                + ". Allowed fields: "
                + allowed_str
            )

        def iter_rows() -> Iterable[List[str]]:
            for obj in queryset:
                service_type = obj.service_type
                mapping = {
                    "id": str(obj.id),
                    "user_id": str(obj.user_id),
                    "user_email": getattr(obj.user, "email", None),
                    "user_first_name": getattr(obj.user, "first_name", None),
                    "user_last_name": getattr(obj.user, "last_name", None),
                    "service_type_id": str(service_type.id) if service_type else None,
                    "service_type_name": service_type.name if service_type else None,
                    "service_type_price_usd": (
                        str(service_type.price_usd) if service_type else None
                    ),
                    "status": obj.status,
                    "reserved_amount": str(obj.reserved_amount),
                    "created": obj.created.strftime("%Y-%m-%d %H:%M:%S") if obj.created else "",
                    "updated": obj.updated.strftime("%Y-%m-%d %H:%M:%S") if obj.updated else "",
                }
                yield [mapping.get(field) for field in requested_fields]

        return requested_fields, iter_rows()


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
            # Send notification about insufficient balance (no commit needed, just async)
            from apps.billing.tasks import send_insufficient_balance_notification
            
            send_insufficient_balance_notification.delay(
                user_id=str(user.id),
                service_type_id=str(service_type.id),
                required_amount=str(service_type.price_usd),
                current_balance=str(current_balance),
            )
            
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
        from apps.billing.tasks import auto_confirm_service_request, send_service_request_created_notification
        
        timeout_seconds = getattr(settings, "BILLING_AUTO_CONFIRM_TIMEOUT", 120)  # Default: 2 minutes
        
        # Schedule tasks after transaction commit
        db_transaction.on_commit(
            lambda: auto_confirm_service_request.apply_async(
                args=[str(service_request.id)],
                countdown=timeout_seconds,
            )
        )
        
        # Send notification about created request after commit
        db_transaction.on_commit(
            lambda: send_service_request_created_notification.delay(str(service_request.id))
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
        
        # Send notification about status change after commit.
        # NB: service_request.status is stored as a string (choice field),
        # so we pass the raw value here. The Celery task converts it back
        # to ServiceStatus enum internally.
        from apps.billing.tasks import send_service_request_status_changed_notification
        
        db_transaction.on_commit(
            lambda: send_service_request_status_changed_notification.delay(
                service_request_id=str(service_request.id),
                old_status=old_status,
                new_status=new_status_enum.value,
            )
        )
        
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

        transaction = BalanceTransaction.objects.create(
            user=user,
            direction=TransactionDirection.IN,
            kind=TransactionKind.TOPUP,
            amount=amount,
            external_id=external_id,
        )
        
        # Send notification about balance topup after transaction commit
        from apps.billing.tasks import send_balance_topup_notification
        
        db_transaction.on_commit(
            lambda: send_balance_topup_notification.delay(
                user_id=str(user.id),
                transaction_id=str(transaction.id),
            )
        )
        
        return transaction
