from django.conf import settings
from django.db import models
from django.db.models.fields import PositiveSmallIntegerField
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from site_name.core.models import BaseUuidModel
from site_name.subscription.constants import PaymentStatus


class Plan(BaseUuidModel):
    name = models.CharField(max_length=25, unique=True, db_index=True)
    monthly_price = models.FloatField(default=0.0)
    amount_products_per_week = models.IntegerField()

    description = models.CharField(max_length=500, null=True, blank=True)

    is_trial = models.BooleanField(
        default=False,
    )  # defining if this plan is free forever (must be only one!!!)
    status = models.BooleanField(default=True)
    payment_plan_id = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return f"{self.name}: {self.amount_products_per_week}"

    class Meta:
        ordering = ("monthly_price",)
        verbose_name = _("Plan")
        verbose_name_plural = _("Plans")


class Subscription(BaseUuidModel):
    payment_subscription_id = models.CharField(max_length=128, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )

    plan = models.ForeignKey(
        "subscription.Plan",
        on_delete=models.DO_NOTHING,
        related_name="plan_subscriptions",
    )
    scheduled_plan = models.ForeignKey(
        "subscription.Plan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_subscriptions",
    )

    start_date = models.DateTimeField(auto_now_add=True)
    expire_date = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True)

    paid_amount = models.PositiveIntegerField(null=True)
    status = PositiveSmallIntegerField(choices=PaymentStatus.choices, default=PaymentStatus.FAILED)

    def __str__(self):
        active = "Active" if self.active else "Inactive"
        return f"{self.user} || {self.plan}: {active} "

    @property
    def active(self):
        sub_end_date = self.expire_date or self.next_payment_date
        return (
            False
            if self.status
            not in [PaymentStatus.PAID, PaymentStatus.PAID_CANCELED, PaymentStatus.TRIAL]
            or (sub_end_date and sub_end_date < now())
            else True
        )

    @property
    def object_status(self):
        return self.status, PaymentStatus(PaymentStatus).name  # TODO: test this refactoring

    def mark_sub_as_canceled_or_expired(self):
        self.status = PaymentStatus.CANCELED
        self.next_payment_date = None
        self.scheduled_plan = None
        self.expire_date = now()
        self.save()

    def save(self, *args, **kwargs):
        if not self.paid_amount:
            self.paid_amount = int(self.plan.monthly_price * 100)
        super().save(*args, **kwargs)

        if (
            self.user.subscriptions.filter(
                status__in=[
                    PaymentStatus.PAID,
                    PaymentStatus.PAID_CANCELED,
                    PaymentStatus.PENDING,
                    PaymentStatus.TRIAL,
                ],
            ).count()
            >= 1
        ):
            self.user.onboarding_finished = True
            self.user.save()

    class Meta:
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")
        ordering = ("-created",)
