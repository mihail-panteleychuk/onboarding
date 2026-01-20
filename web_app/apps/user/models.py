from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from apps.core.models import BaseUuidModel
from apps.core.utils import send_confirm_email_message


class User(AbstractBaseUser, PermissionsMixin, BaseUuidModel):
    class UserRoleChoices(models.IntegerChoices):
        USER = (1, "User")
        ADMIN = (2, "Admin")
        MANAGER = (3, "Manager")
        FREE_ACCESS = (4, "Free access")

    role = models.PositiveSmallIntegerField(
        choices=UserRoleChoices.choices,
        default=UserRoleChoices.USER,
    )
    email = models.EmailField(max_length=255, null=False, unique=True, db_index=True)
    first_name = models.CharField(max_length=124, null=True)
    last_name = models.CharField(max_length=124, null=True)
    avatar = models.FileField(upload_to="avatars", null=True, blank=True)
    email_subscribed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    phone_code = models.ForeignKey(
        "user.Country",
        on_delete=models.SET_DEFAULT,
        related_name="user_phones",
        null=True,
        blank=True,
        default=None,
    )
    phone = models.CharField(max_length=64, null=True, blank=True)
    facebook_user_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
    )
    apple_user_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
    )
    google_user_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
    )
    onboarding_finished = models.BooleanField(
        default=False,
        help_text="Flag for defining if user can access site (all sign up steps are finished)",
    )
    language = models.CharField(
        choices=settings.LANGUAGES,
        default="en",
        max_length=30,
        help_text="Field for detecting language for responses",
    )
    payment_service_user_id = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="Unique identifier of user on PaymentService",
    )

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ("-created",)

    objects = UserManager()
    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"

    @property
    def full_name(self):
        return (
            f"{self.first_name or ''} {self.last_name or ''}"
            if any([self.first_name, self.last_name])
            else None
        )

    @property
    def get_role_object(self):
        return {"id": self.role, "name": User.UserRoleChoices(self.role).label}

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        if self._state.adding and User.objects.filter(email__iexact=self.email.lower()).exists():
            msg = (
                f"User with {self.email} already exists on the website. "
                "Please try another email address or contact the user."
            )
            raise ValidationError({"detail": msg})

        # user password encrypting if it was set new
        self.password = self.password or settings.DEFAULT_PASSWORD
        if (
            self.password
            and not self.password.startswith("pbkdf2_sha256$216000$")
            and len(self.password.split("$")) != 4
        ):
            self.set_password(self.password)

        if self._state.adding and not self.is_active:
            link = "https://" + settings.FRONT_DOMAIN + "/sign-up/confirm/{}"
            send_confirm_email_message(self, link, "confirm_email.html")
        if self._state.adding:
            self.onboarding_finished = self.role != self.UserRoleChoices.USER

        super().save(*args, **kwargs)


class Country(models.Model):
    name = models.CharField(max_length=256)
    flag = models.FileField(upload_to="country_flags/", null=True, blank=True)
    code = models.CharField(max_length=256, null=True, blank=True)
    state = models.JSONField(null=True, blank=True, default=None)
    country_code = models.CharField(max_length=5, null=True)

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")

    def __str__(self):
        return self.name


class ConfirmCode(BaseUuidModel):
    user = models.ForeignKey("user.User", on_delete=models.CASCADE)
    code = models.BigIntegerField()
    expiring_date = models.DateTimeField()
    new_email = models.EmailField(max_length=255, null=True, blank=True, default=None)
    new_password = models.CharField(max_length=120, null=True, blank=True, default=None)

    def __str__(self):
        return f"{self.user.email} || {self.code}"

    class Meta:
        verbose_name = _("Confirm code")
        verbose_name_plural = _("Confirm cods")


class CompanyDetails(BaseUuidModel):
    user = models.OneToOneField(
        "user.User",
        on_delete=models.CASCADE,
        related_name="company",
        unique=True,
        db_index=True,
    )
    country = models.ForeignKey("user.Country", on_delete=models.CASCADE, related_name="companies")

    name = models.CharField(max_length=128)
    city = models.CharField(max_length=128, db_index=True)
    state = models.CharField(max_length=128, null=True, blank=True)
    postal_code = models.CharField(max_length=16)
    address_line_1 = models.CharField(max_length=128)
    address_line_2 = models.CharField(max_length=128, null=True, blank=True)
    VAT = models.CharField(max_length=128, null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = _("User Company Details")
        verbose_name_plural = _("Users Company Details")

    def __str__(self):
        return (
            f"{self.name} : {self.country}, {self.city}, {self.address_line_1}" + ""
            if not self.address_line_2
            else f", {self.address_line_2}"
        )
