# from django.db.models import Q, F
# from django.db.models.functions import Now
# from payments.utils import register_chargebee_customer, remove_customer, update_customer_billing_info, update_user_email
from django.contrib.auth.models import (AbstractBaseUser, UserManager,
                                        PermissionsMixin)
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.db import models
from core.models import BaseUuidModel

class User(AbstractBaseUser, PermissionsMixin, BaseUuidModel):
    USER = 1
    ADMIN = 2
    MANAGER = 3
    FREE_ACCESS = 4

    ROLE_CHOICES = (
        (USER, 'User'),
        (ADMIN, 'Admin'),
        (MANAGER, 'Manager'),
        (FREE_ACCESS, 'Free Access'),
    )

    # base user fields
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, default=USER)
    email = models.EmailField(max_length=255, null=False, unique=True, db_index=True)
    first_name = models.CharField(max_length=124, null=True, blank=True)
    last_name = models.CharField(max_length=124,  null=True, blank=True)
    avatar = models.FileField(upload_to='avatars', null=True, blank=True)

    email_confirmed = models.BooleanField(default=False)
    email_subscribed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    # flags for django admin access
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # user emails from social accounts
    facebook_user_id = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True)
    apple_user_id = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True)
    google_user_id = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True)

    # flag for defining if user can access site (all sign up steps are finished)
    onboarding_finished = models.BooleanField(default=False)
    # field for detecting language for responses
    language = models.CharField(choices=settings.LANGUAGES, default='en', max_length=30)
    # unique identifier of user on PaymentService
    payment_service_user_id = models.CharField(max_length=128, null=True, blank=True)


    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    objects = UserManager()
    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'

    @property
    def get_role_object(self):
        return {
            'id': self.role,
            'name': dict(User.ROLE_CHOICES)[self.role]
        }

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        # user password encrypting if it was set new
        if not self.password.startswith('pbkdf2_sha256$216000$') and len(self.password.split('$')) != 4 and self.password:
            self.set_password(self.password)

        super(User, self).save(*args,**kwargs)
        # update_user_email(self)


class Country(models.Model):
    name = models.CharField(max_length=256)
    flag = models.FileField(upload_to='country_flags/', null=True, blank=True)
    code = models.CharField(max_length=256, null=True, blank=True)
    state = models.JSONField(null=True, blank=True, default=None)
    country_code = models.CharField(max_length=5, null=True)

    class Meta:
        verbose_name = _('Country')
        verbose_name_plural = _('Countries')

    def __str__(self):
        return self.name


class BillingAddress(models.Model):
    user = models.OneToOneField('user.User', primary_key=True, on_delete=models.CASCADE, related_name='user_billing')

    first_name = models.CharField(max_length=124, null=True, blank=True)
    last_name = models.CharField(max_length=124,  null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=124, null=True, blank=True)
    country = models.ForeignKey('user.Country', on_delete=models.SET_DEFAULT, related_name='users_address', null=True, default=None)
    postal_code = models.CharField(max_length=50, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)

    phone = models.PositiveBigIntegerField(null=True, blank=True)
    phone_code = models.ForeignKey('user.Country', on_delete=models.SET_DEFAULT, related_name='users_phone_code', null=True, blank=True, default=None)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Billing address')
        verbose_name_plural = _('Billing address')

    def __str__(self):
        return self.user.email


class ConfirmCode(BaseUuidModel):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    code = models.BigIntegerField()
    expiring_date = models.DateTimeField()
    new_email = models.EmailField(max_length=255, null=True, blank=True, default=None)
    new_password = models.CharField(max_length=120, null=True,blank=True, default=None)

    def __str__(self):
        return self.user.email

    class Meta:
        verbose_name = _('Confirm code')
        verbose_name_plural = _('Confirm cods')


class CompanyDetails(BaseUuidModel):
    user = models.OneToOneField('user.User', on_delete=models.CASCADE, related_name='company', unique=True, db_index=True)
    country = models.ForeignKey('user.Country', on_delete=models.CASCADE, related_name='companies')

    name = models.CharField(max_length=128)
    city = models.CharField(max_length=128, db_index=True)
    state = models.CharField(max_length=128, null=True, blank=True)
    postal_code = models.CharField(max_length=16)
    address_line_1 = models.CharField(max_length=128)
    address_line_2 = models.CharField(max_length=128, null=True, blank=True)
    VAT = models.CharField(max_length=128, null=True, blank=True, db_index=True)



    class Meta:
        verbose_name = _('User Company Details')
        verbose_name_plural = _('Users Company Details')

    def __str__(self):
        return f"{self.name} : {self.country}, {self.city}, {self.address_line_1}" + '' if not self.address_line_2 else f", {self.address_line_2}"



# POST USER CREATE SIGNAL
@receiver(post_save, sender=get_user_model())
def create_user_notifications_settings_and_payment_customer(sender, instance, created, **kwargs):
    """
        Add other default related objects creating on new user creating if needeed
        example: create user profile on payments service
    """
    if created:
        # to something
        pass




