from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from random import randint
from smtplib import SMTP
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta
from django.apps import apps


def send_restore_password_email(receiver, html_template, subject=None, txt_template=None):
    ConfirmCode = apps.get_model('user.ConfirmCode')
    confirm_code = ConfirmCode.objects.filter(user=receiver).first()
    if not confirm_code:
        confirm_code = ConfirmCode(user=receiver)
    confirm_code.code = randint(111111, 999999)
    confirm_code.expiring_date = now() + timedelta(hours=3)
    confirm_code.save()

    context = {'code': confirm_code.code}

    send_custom_email(
        receiver,
        context,
        subject or 'Reset your password',
        html_template,
        txt_template=txt_template
    )


def send_confirm_email_message(receiver, link_pattern,  html_template, subject=None, txt_template=None):

    ConfirmCode = apps.get_model('user.ConfirmCode')

    confirm_code, created = ConfirmCode.objects.get_or_create(user=receiver,
                                                     expiring_date__gt=now(),
                                                     defaults = {
                                                         'expiring_date': now() + timedelta(hours=24),
                                                         'code': randint(1111111111, 9999999999),
                                                     })


    link = link_pattern.format(confirm_code.code)
    context = {'link': link}
    send_custom_email(
        receiver,
        context,
        subject or 'Confirm your email',
        html_template,
        txt_template=txt_template
    )



def send_custom_email(receiver, context, subject, html_template, txt_template=None):
    msg = MIMEMultipart('alternative')  # this is special format for email messages

    msg['Subject'] = subject
    _from = f"InHome Dataforest <{settings.EMAIL_HOST_USER}>"
    msg['From'] = _from
    msg['To'] = receiver.email

    html = render_to_string(html_template, context)
    part2 = MIMEText(html, 'html')
    msg.attach(part2)

    server = SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
    server.starttls()
    server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
    server.sendmail(settings.EMAIL_HOST, receiver.email, msg.as_string())
    server.quit()
