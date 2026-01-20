import logging
import time

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from apps.core.app_context import app_context

logger = logging.getLogger(__name__)


@shared_task
def task_dummy(a, b):
    result = int(a) + int(b)
    logger.info(
        f"This log is from task started in trace_id='{app_context.trace_id}' "
        f"by user_id='{app_context.user_id}': '{a} + {b} = {result}'",
    )
    return result


@shared_task
def task_dummy_delay(delay):
    logger.info(f"This log is from task with delay={delay}s")
    time.sleep(delay)


@shared_task
def task_dummy_exception():
    logger.info("This task will raise an exception")
    raise Exception("This is a test exception")


@shared_task
def send_email(email: str, title: str, template_name: str, data_for_template: dict = None) -> bool:
    """
    Asynchronously sends an email with the specified title, template, and data using Celery.

    Args:
        email (str): The recipient's email address.
        title (str): The subject of the email.
        template_name (str): The name of the HTML template for the email content.
        data_for_template (dict, optional): The context data to be rendered in the template. Defaults to None.

    Returns:
        bool: True if the email is sent successfully.
    """
    subject, to = title, email
    html_message = render_to_string(template_name, data_for_template)
    from_email = f"InHome Dataforest <{settings.EMAIL_HOST_USER}>"
    message = EmailMultiAlternatives(
        subject=subject,
        body=html_message,
        from_email=from_email,
        to=[to],
    )
    message.mixed_subtype = "related"
    message.attach_alternative(html_message, "text/html")
    message.send(fail_silently=False)
    return True
