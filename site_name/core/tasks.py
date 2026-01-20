from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from site_name.config.celery import celery_app


@celery_app.task
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
