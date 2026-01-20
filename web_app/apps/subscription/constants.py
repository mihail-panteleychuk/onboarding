from django.db import models


class PaymentStatus(models.IntegerChoices):
    FAILED = 0, "Failed"
    PAID = 1, "Paid"
    PENDING = 2, "Pending"
    CANCELED = 3, "Canceled"
    SCHEDULED = 4, "Scheduled"
    PAID_CANCELED = 5, "Canceling Scheduled"
    TRIAL = 6, "Trial"

    @property
    def active_statuses(self):
        return [self.PAID, self.PAID_CANCELED, self.PENDING, self.TRIAL]
