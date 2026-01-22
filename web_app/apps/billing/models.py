"""Billing models: internal user balance and service requests."""

from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import models
from django.db.models import Case, F, Sum, When

from apps.core.models import BaseUuidModel
from apps.billing.constants import ServiceStatus, TransactionDirection, TransactionKind


class ServiceType(BaseUuidModel):
    """Represents a fixed type of service with a predefined price in USD."""

    name: models.CharField = models.CharField(
        max_length=255,
        unique=True,
        help_text="Human‑readable service name (e.g. Cleaning, Plumber, Electrician).",
    )
    price_usd: models.DecimalField = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Service price in USD.",
    )
    is_active: models.BooleanField = models.BooleanField(
        default=True,
        help_text="Whether this service type is available for new requests.",
    )

    class Meta:
        verbose_name = "Service type"
        verbose_name_plural = "Service types"
        ordering = ("name",)

    def __str__(self) -> str:
        """Return a human‑readable representation."""
        return f"{self.name} ({self.price_usd} USD)"


class BalanceTransactionQuerySet(models.QuerySet):
    """Custom queryset for balance transactions."""

    def for_user(self, user) -> "BalanceTransactionQuerySet":
        """Filter transactions for a specific user."""
        return self.filter(user=user)
        

    def calculate_balance(self) -> Decimal:
        """
        Calculate total balance from transactions.        
        Note: CAPTURE transactions are excluded from balance calculation
        because RESERVE already decreased the balance. CAPTURE is for history only.
        """
        total = (
            self.exclude(kind=TransactionKind.CAPTURE)  # Exclude CAPTURE (already accounted in RESERVE)
            .annotate(
                effective_amount=Case(
                    When(direction=TransactionDirection.IN, then=F("amount")),
                    When(direction=TransactionDirection.OUT, then=-F("amount")),
                )
            )
            .aggregate(balance=Sum("effective_amount"))["balance"]
            or Decimal("0")
        )
        return total


class BalanceTransactionManager(models.Manager):
    """Custom manager for balance transactions."""

    def get_queryset(self) -> BalanceTransactionQuerySet:
        """Return custom queryset."""
        return BalanceTransactionQuerySet(self.model, using=self._db)

    
    def for_user(self, user) -> BalanceTransactionQuerySet:
        """Filter transactions for a specific user."""
        return self.get_queryset().for_user(user)

    
    def calculate_user_balance(self, user) -> Decimal:
        """Calculate current balance for a user."""
        return self.for_user(user).calculate_balance()


class BalanceTransaction(BaseUuidModel):
    """Single balance operation for a user (top‑up, reserve, capture, refund)."""

    user: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="billing_transactions",
        help_text="User whose balance is affected by this transaction.",
    )
    direction: models.CharField = models.CharField(
        max_length=8,
        choices=TransactionDirection.choices,
        help_text="Direction of money flow: IN (credit) or OUT (debit).",
    )
    kind: models.CharField = models.CharField(
        max_length=16,
        choices=TransactionKind.choices,
        help_text="Business meaning of the transaction.",
    )
    amount: models.DecimalField = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Absolute amount in USD (always positive).",
    )
    service_request: models.ForeignKey = models.ForeignKey(
        "billing.ServiceRequest",
        on_delete=models.CASCADE,
        related_name="transactions",
        null=True,
        blank=True,
        help_text="Related service request for reserve/charge/refund operations.",
    )
    external_id: models.CharField = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Optional external identifier (e.g. Stripe session id).",
    )

    objects = BalanceTransactionManager()

    class Meta:
        verbose_name = "Balance transaction"
        verbose_name_plural = "Balance transactions"
        ordering = ("-created",)
        indexes = [
        ]

    
    def __str__(self) -> str:
        """Return a readable description of the transaction."""
        return f"{self.user_id} {self.direction} {self.amount} ({self.kind})"

    
    @property
    def signed_amount(self) -> Decimal:
        """Return amount with sign based on direction (IN = +, OUT = -)."""
        
        if self.direction == TransactionDirection.IN:
            return self.amount

        return -self.amount


class ServiceRequestQuerySet(models.QuerySet):
    """Custom queryset for service requests."""

    def for_user(self, user) -> "ServiceRequestQuerySet":
        """Filter requests for a specific user."""
        return self.filter(user=user)


    def for_admin(self) -> "ServiceRequestQuerySet":
        """Return all requests (for admin)."""
        return self.all()


class ServiceRequestManager(models.Manager):
    """Custom manager for service requests."""

    def get_queryset(self) -> ServiceRequestQuerySet:
        """Return custom queryset."""
        return ServiceRequestQuerySet(self.model, using=self._db)


    def for_user(self, user) -> ServiceRequestQuerySet:
        """Filter requests for a specific user."""
        return self.get_queryset().for_user(user)
        

    def for_admin(self) -> ServiceRequestQuerySet:
        """Return all requests (for admin)."""
        return self.get_queryset().for_admin()


class ServiceRequest(BaseUuidModel):
    """Represents a user's request for a particular service type."""

    user: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="service_requests",
        help_text="User who created the service request.",
    )
    service_type: models.ForeignKey = models.ForeignKey(
        ServiceType,
        on_delete=models.PROTECT,
        related_name="requests",
        help_text="Requested service type.",
    )
    status: models.CharField = models.CharField(
        max_length=16,
        choices=ServiceStatus.choices,
        default=ServiceStatus.PENDING,
        db_index=True,
        help_text="Current status in the request lifecycle.",
    )
    reserved_amount: models.DecimalField = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Amount reserved from user balance when the request was created (USD).",
    )

    objects = ServiceRequestManager()

    class Meta:
        verbose_name = "Service request"
        verbose_name_plural = "Service requests"
        ordering = ("-created",)

    
    def __str__(self) -> str:
        """Return a human‑readable representation of the request."""
        return f"{self.user_id} → {self.service_type.name} [{self.status}]"

    
    def can_be_cancelled_by_user(self) -> bool:
        """Check if request can be cancelled by user."""
        return self.status == ServiceStatus.PENDING

    
    def reserve_funds(self) -> "BalanceTransaction":
        """Reserve funds from user balance for this request.
        Creates a RESERVE transaction (OUT direction) for the service price. """
        
        if self.reserved_amount > Decimal("0"):
            raise ValueError("Funds are already reserved for this request.")

        if self.status != ServiceStatus.PENDING:
            raise ValueError(f"Cannot reserve funds for request with status {self.status}.")

        transaction = BalanceTransaction.objects.create(
            user=self.user,
            direction=TransactionDirection.OUT,
            kind=TransactionKind.RESERVE,
            amount=self.service_type.price_usd,
            service_request=self,
        )

        self.reserved_amount = self.service_type.price_usd
        self.save(update_fields=["reserved_amount"])
        return transaction

    
    def refund_reserved_funds(self) -> Optional["BalanceTransaction"]:
        """Refund reserved funds back to user balance.
        Creates a REFUND transaction (IN direction) if funds were reserved.
        """
        
        if self.reserved_amount <= Decimal("0"):
            return None

        transaction = BalanceTransaction.objects.create(
            user=self.user,
            direction=TransactionDirection.IN,
            kind=TransactionKind.REFUND,
            amount=self.reserved_amount,
            service_request=self,
        )

        self.reserved_amount = Decimal("0.00")
        self.save(update_fields=["reserved_amount"])
        return transaction


    def cancel(self) -> Optional["BalanceTransaction"]:
        """Cancel the request and refund reserved funds.
        Changes status to CANCELLED and refunds reserved funds if any."""
        
        if self.status == ServiceStatus.CANCELLED:
            return None

        self.status = ServiceStatus.CANCELLED
        self.save(update_fields=["status"])
        return self.refund_reserved_funds()
        