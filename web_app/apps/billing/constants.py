"""Constants and choice enums for the billing domain."""

from django.db import models


class ServiceStatus(models.TextChoices):
    """Lifecycle statuses for a service request."""

    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class TransactionDirection(models.TextChoices):
    """Direction of money flow for a balance transaction."""

    IN = "in", "In"        # credit: top‑up or refund
    OUT = "out", "Out"     # debit: reserve or charge


class TransactionKind(models.TextChoices):
    """Business meaning of a balance transaction."""

    TOPUP = "topup", "Top up"          # balance top‑up via Stripe
    RESERVE = "reserve", "Reserve"     # money reserved for a service request
    CAPTURE = "capture", "Capture"     # final charge for a confirmed request
    REFUND = "refund", "Refund"        # refund of a previous reserve/charge
