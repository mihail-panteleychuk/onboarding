import logging
from datetime import timedelta
from random import randint

from django.apps import apps
from django.utils import timezone

from apps.core.app_context import app_context
from apps.core.tasks import send_email


def send_restore_password_email(receiver, html_template: str, subject: str = None):
    """
    Sends an email to a user with a code to restore their password.

    Args:
        receiver (User): The user who will receive the email.
        html_template (str): The HTML template to be used for the email.
        subject (str, optional): The subject of the email. Defaults to "Reset your password".

    Returns:
        None
    """
    ConfirmCode = apps.get_model("user.ConfirmCode")  # noqa : N806
    confirm_code = ConfirmCode.objects.filter(user=receiver).first()
    if not confirm_code:
        confirm_code = ConfirmCode(user=receiver)
    confirm_code.code = randint(111111, 999999)
    confirm_code.expiring_date = timezone.now() + timedelta(hours=3)
    confirm_code.save()

    send_email(
        email=receiver.email,
        title=subject or "Reset your password",
        template_name=html_template,
        data_for_template={"code": confirm_code.code},
    )


def send_confirm_email_message(
    receiver,
    link_pattern: str,
    html_template: str,
    subject: str = None,
):
    """
    Sends a confirmation email to a user with a link to confirm their email address.

    Args:
        receiver (User): The user who will receive the email.
        link_pattern (str): The pattern for the confirmation link, where the code will be inserted.
        html_template (str): The HTML template to be used for the email.
        subject (str, optional): The subject of the email. Defaults to "Confirm your email".

    Returns:
        None
    """
    ConfirmCode = apps.get_model("user.ConfirmCode")  # noqa : N806

    confirm_code, created = ConfirmCode.objects.get_or_create(
        user=receiver,
        expiring_date__gt=timezone.now(),
        defaults={
            "expiring_date": timezone.now() + timedelta(hours=24),
            "code": randint(1111111111, 9999999999),
        },
    )

    link = link_pattern.format(confirm_code.code)
    send_email(
        email=receiver.email,
        title=subject or "Confirm your email",
        template_name=html_template,
        data_for_template={"link": link},
    )


class TrackingLogFilter(logging.Filter):
    """
    Logging filter to add `traceid` to log records
    """

    def filter(self, record):
        record.traceid = app_context.trace_id or ""
        record.userid = app_context.user_id or ""

        if app_context.request:
            return bool(app_context.logging_enabled)

        # NOTE: enable logging for all non-request processes (Like app boot-up or smth else)
        return True
