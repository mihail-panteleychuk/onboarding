from core.models import BaseUuidModel
from core.utils import send_confirm_email_message
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError


class User(AbstractBaseUser, PermissionsMixin, BaseUuidModel):
    USER = 1
    ADMIN = 2

    ROLE_CHOICES = (
        (USER, "User"),
        (ADMIN, "Admin"),
    )

    # base user fields
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, default=USER)
    email = models.EmailField(max_length=255, null=False, unique=True, db_index=True)
    first_name = models.CharField(max_length=124, null=True)
    last_name = models.CharField(max_length=124, null=True)

    email_subscribed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    # flags for django admin access
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # phone info
    phone = models.CharField(max_length=64, null=True, blank=True)

    # user emails from social accounts
    facebook_user_id = models.CharField(
        max_length=50, unique=True, db_index=True, null=True, blank=True
    )
    apple_user_id = models.CharField(
        max_length=50, unique=True, db_index=True, null=True, blank=True
    )
    google_user_id = models.CharField(
        max_length=50, unique=True, db_index=True, null=True, blank=True
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
            f"{self.first_name or '' } {self.last_name or ''}"
            if any([self.first_name, self.last_name])
            else None
        )

    @property
    def get_role_object(self):
        return {"id": self.role, "name": dict(User.ROLE_CHOICES)[self.role]}

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

        super().save(*args, **kwargs)


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
