# Generated manually for billing app

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceType",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        help_text="Human‑readable service name (e.g. Cleaning, Plumber, Electrician).",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "price_usd",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Service price in USD.",
                        max_digits=10,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this service type is available for new requests.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Service type",
                "verbose_name_plural": "Service types",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="ServiceRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("confirmed", "Confirmed"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="pending",
                        help_text="Current status in the request lifecycle.",
                        max_length=16,
                    ),
                ),
                (
                    "reserved_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=0.0,
                        help_text="Amount reserved from user balance when the request was created (USD).",
                        max_digits=10,
                    ),
                ),
                (
                    "service_type",
                    models.ForeignKey(
                        help_text="Requested service type.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="requests",
                        to="billing.servicetype",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="User who created the service request.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Service request",
                "verbose_name_plural": "Service requests",
                "ordering": ("-created",),
            },
        ),
        migrations.CreateModel(
            name="BalanceTransaction",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "direction",
                    models.CharField(
                        choices=[("in", "In"), ("out", "Out")],
                        help_text="Direction of money flow: IN (credit) or OUT (debit).",
                        max_length=8,
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("topup", "Top up"),
                            ("reserve", "Reserve"),
                            ("capture", "Capture"),
                            ("refund", "Refund"),
                        ],
                        help_text="Business meaning of the transaction.",
                        max_length=16,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Absolute amount in USD (always positive).",
                        max_digits=10,
                    ),
                ),
                (
                    "external_id",
                    models.CharField(
                        blank=True,
                        help_text="Optional external identifier (e.g. Stripe session id).",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "service_request",
                    models.ForeignKey(
                        blank=True,
                        help_text="Related service request for reserve/charge/refund operations.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transactions",
                        to="billing.servicerequest",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="User whose balance is affected by this transaction.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billing_transactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Balance transaction",
                "verbose_name_plural": "Balance transactions",
                "ordering": ("-created",),
            },
        ),
    ]
