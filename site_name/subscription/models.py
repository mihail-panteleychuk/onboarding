from django.db import models
from django.conf import settings
from django.utils.timezone import now
import datetime
from django.db.models.fields import PositiveSmallIntegerField
from .constants import (PAYMENT_STATUSES, STATUS_FAILED,
                        STATUS_PAID, STATUS_PAID_CANCELED,
                        STATUS_PENDING, STATUS_TRIAL)
from django.utils.translation import gettext_lazy as _

from core.models import BaseUuidModel
class Plan(BaseUuidModel):
    name = models.CharField(max_length=25, unique=True, db_index=True)
    monthly_price = models.FloatField(default=0.0)
    amount_products_per_week = models.IntegerField()

    is_trial = models.BooleanField(default=False)   # defining if this plan is free forever (must be only one!!!)
    status = models.BooleanField(default=True)
    payment_plan_id = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.amount_products_per_week}"

    class Meta:
        ordering = ('monthly_price',)
        verbose_name = _("Plan")
        verbose_name_plural = _("Plans")


class Subscription(BaseUuidModel):
    payment_subscription_id = models.CharField(max_length=128, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')

    plan = models.ForeignKey('subscription.Plan', on_delete=models.DO_NOTHING, related_name='plan_subscriptions')
    scheduled_plan = models.ForeignKey('subscription.Plan', on_delete=models.SET_NULL, null=True, blank=True, related_name='scheduled_subscriptions')

    start_date = models.DateTimeField(auto_now_add=True)
    expire_date = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True)

    paid_amount = models.PositiveIntegerField(null=True)
    status = PositiveSmallIntegerField(choices=PAYMENT_STATUSES, default=STATUS_FAILED)

    def __str__(self):
        active = 'Active' if self.active  else 'Inactive'
        return f'{self.pk} | {self.user}: {self.category}--{self.plan.amount_products_per_week}: {active} '

    @staticmethod
    def get_choice_object(object_id, choices):
        if object_id or isinstance(object_id, int):
            return {
                'id': object_id,
                'name': dict(choices)[object_id]
            }
        return None

    @property
    def active(self):
        sub_end_date = self.expire_date or self.next_payment_date
        return False if self.status not in [STATUS_PAID, STATUS_PAID_CANCELED, STATUS_TRIAL] or ( sub_end_date and sub_end_date < now()) else True

    @property
    def object_status(self):
        return self.get_choice_object(self.status, PAYMENT_STATUSES)

    def save(self, *args, **kwargs):
        super(Subscription, self).save(*args, **kwargs)

        if not any([self.next_payment_date, self.expire_date]):
            if self.status in [STATUS_PAID, STATUS_PENDING]:
                self.next_payment_date = self.start_date + datetime.timedelta(days=30)
                self.expire_date = None
            else:
                self.next_payment_date = None
                self.expire_date = self.start_date + datetime.timedelta(days=30)

        if self.status in [STATUS_PAID, STATUS_PAID_CANCELED, STATUS_TRIAL]:
            ## processing active subscription
            start_time = self.start_date if self.start_date else now()
            if self.status == STATUS_TRIAL:
                self.expire_date = self.expire_date or self.next_payment_date
                self.next_payment_date = None
            else:
                self.next_payment_date = start_time + datetime.timedelta(days=30) if not self.next_payment_date and not self.expire_date else self.next_payment_date
            # drops = Drop.objects\
            #     .filter(Q(drop_date__lte=self.next_payment_date or self.expire_date))\
            #     .filter(drop_date__gte=self.start_date,
            #             plan_id=self.plan.id)

            # self.user.user_drops.add(*drops)
        elif self.status in [STATUS_PENDING, STATUS_FAILED]:
            ## processing NOT active subscription  obj
            # drops = Drop.objects\
            #     .filter(Q(drop_date__lte=self.next_payment_date or self.expire_date))\
            #     .filter(drop_date__gte=self.start_date - timedelta(days=7),
            #             plan_id=self.plan.id)
            if self.status == STATUS_FAILED:
                self.next_payment_date = None
                self.expire_date = self.start_date
            # self.user.user_drops.remove(*drops)

        if not self.paid_amount:
            self.paid_amount = int(self.plan.monthly_price * 100)
        super(Subscription, self).save(*args, **kwargs)


    class Meta:
        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')

