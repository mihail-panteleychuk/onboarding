from django.db import models

from site_name.core.models import BaseUuidModel
from site_name.subscription.models import PaymentStatus, Subscription


class Card(BaseUuidModel):
    brand = models.CharField(max_length=128)
    country = models.ForeignKey(
        "user.Country",
        related_name="cards",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    exp_month = models.IntegerField()
    exp_year = models.IntegerField()
    last4 = models.CharField(max_length=4, null=False, blank=False)

    user = models.ForeignKey(
        "user.User",
        related_name="cards",
        on_delete=models.CASCADE,
        db_index=True,
    )

    payment_method_id = models.CharField(max_length=128, null=True)

    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email}: {self.last4}. Active: {self.active}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.active:
            self.user.cards.exclude(pk=self.id).update(active=False)

    class Meta:
        ordering = ("-created",)


class BillingAddress(BaseUuidModel):
    card = models.OneToOneField(
        "payments.Card",
        on_delete=models.CASCADE,
        related_name="card_billing",
    )

    first_name = models.CharField(max_length=124, null=True, blank=True)
    last_name = models.CharField(max_length=124, null=True, blank=True)
    address_line_1 = models.CharField(max_length=255, null=True, blank=True)
    address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=124, null=True, blank=True)
    country = models.ForeignKey(
        "user.Country",
        on_delete=models.SET_DEFAULT,
        related_name="users_address",
        null=True,
        default=None,
    )
    postal_code = models.CharField(max_length=50, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        verbose_name = "Billing address"
        verbose_name_plural = "Billing address"
        ordering = ("-created",)

    def __str__(self):
        country_name = self.country.name if self.country else None
        return f"{country_name}, {self.state}, {self.city}, {self.address_line_1}"


class InvoiceLineItem(BaseUuidModel):
    subscription = models.ForeignKey(
        "subscription.Subscription",
        related_name="invoice_lines",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    invoice = models.ForeignKey(
        "payments.Invoice",
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    description = models.CharField(max_length=256, null=True, blank=True)

    price = models.IntegerField(default=0)
    discount = models.IntegerField(default=0)

    def __str__(self):
        price = round(self.price / 100, 2)
        return f"{self.subscription} :: ${price}"

    class Meta:
        ordering = ("-created",)


class Invoice(models.Model):
    invoice_id = models.CharField(max_length=128, unique=True, primary_key=True)

    credits_applied = models.IntegerField(
        default=0,
    )  # sum of applied credits from existing subscription (force upgrade)
    discount = models.IntegerField(default=0)  # value of discounts applied by coupon
    total = models.IntegerField(default=0)

    issued_date = models.DateField()
    issued = models.DateTimeField()

    status = models.PositiveSmallIntegerField(
        choices=PaymentStatus.choices,
        default=PaymentStatus.FAILED,
    )

    card = models.ForeignKey("payments.Card", on_delete=models.CASCADE, related_name="invoices")
    user = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="invoices")

    def get_status_object(self):
        if self.status or isinstance(self.status, int):
            return {"id": self.status, "name": PaymentStatus(self.status)}
        return None

    class Meta:
        ordering = ("-issued",)

    def update_obj(self, data: dict) -> None:
        for attr, value in data.items():
            setattr(self, attr, value)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        Subscription.objects.filter(invoice_lines__invoice=self).update(status=self.status)
