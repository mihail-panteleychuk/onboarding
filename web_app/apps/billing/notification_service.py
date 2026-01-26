"""Notification service for billing operations."""

import logging
from decimal import Decimal
from typing import Optional

import requests
from django.conf import settings
from django.core.mail import EmailMessage

from apps.billing.constants import ServiceStatus
from apps.billing.models import BalanceTransaction, ServiceRequest

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications (email and Slack) for billing events."""

    @staticmethod
    def send_email_notification(
        recipient_email: str,
        subject: str,
        message: str,
    ) -> bool:
        """Send email notification to user."""
        try:
            # Use default from_email if EMAIL_HOST_USER is not configured
            from_email = getattr(settings, "EMAIL_HOST_USER", "noreply@inhome.com")

            if not from_email:
                from_email = "noreply@inhome.com"
            
            from_email = f"InHome Dataforest <{from_email}>"
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_email,
                to=[recipient_email],
            )
            email.send(fail_silently=False)
            logger.info(f"Email notification sent to {recipient_email}: {subject}")
            return True
        
        except Exception as e:
            logger.error(
                f"Failed to send email notification to {recipient_email}: {str(e)}",
                exc_info=True,
            )
            return False

    @staticmethod
    def send_slack_notification(message: str) -> bool:
        """Send notification to Slack webhook.
        """
        # Check if Slack is enabled
        slack_enabled = getattr(settings, "SLACK_ENABLED", False)
        
        if not slack_enabled:
            logger.debug("Slack notifications are disabled (SLACK_ENABLED=False), skipping")
            return False
        
        webhook_url = getattr(settings, "SLACK_WEBHOOK_URL", None)
        
        if not webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not configured, skipping Slack notification")
            return False
        
        try:
            payload = {"text": message}
            response = requests.post(webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
            return True
        
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to send Slack notification: {str(e)}",
                exc_info=True,
            )
            return False
        
        except Exception as e:
            logger.error(
                f"Unexpected error sending Slack notification: {str(e)}",
                exc_info=True,
            )
            return False


    @staticmethod
    def notify_service_request_created(service_request: ServiceRequest) -> None:
        """Send notifications when a service request is created. """
        user = service_request.user
        service_type = service_request.service_type
        
        # Email to user
        email_subject = f"Service request created: {service_type.name}"
        email_message = (
            f"Hello, {user.first_name or user.email}!\n\n"
            f"Your service request for '{service_type.name}' has been successfully created.\n\n"
            f"Request details:\n"
            f"- Request ID: {service_request.id}\n"
            f"- Service type: {service_type.name}\n"
            f"- Price: {service_type.price_usd} USD\n"
            f"- Reserved amount: {service_request.reserved_amount} USD\n"
            f"- Status: {service_request.status}\n"
            f"- Created at: {service_request.created.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Your balance after reservation: {BalanceTransaction.objects.calculate_user_balance(user)} USD\n\n"
            f"The request is awaiting confirmation."
        )
        NotificationService.send_email_notification(
            recipient_email=user.email,
            subject=email_subject,
            message=email_message,
        )
        
        # Slack to admin
        slack_message = (
            f"🔔 New service request\n\n"
            f"ID: {service_request.id}\n"
            f"User: {user.email} ({user.first_name or ''} {user.last_name or ''})\n"
            f"Service: {service_type.name}\n"
            f"Price: {service_type.price_usd} USD\n"
            f"Reserved: {service_request.reserved_amount} USD\n"
            f"Status: {service_request.status}\n"
            f"Date: {service_request.created.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        NotificationService.send_slack_notification(slack_message)

    
    @staticmethod
    def notify_service_request_status_changed(
        service_request: ServiceRequest,
        old_status: ServiceStatus,
        new_status: ServiceStatus,
    ) -> None:
        """Send notifications when service request status changes.
        """
        user = service_request.user
        service_type = service_request.service_type
        
        status_messages = {
            ServiceStatus.CONFIRMED: {
                "subject": f"Service request confirmed: {service_type.name}",
                "email": (
                    f"Hello, {user.first_name or user.email}!\n\n"
                    f"Your service request for '{service_type.name}' has been confirmed.\n\n"
                    f"Request details:\n"
                    f"- Request ID: {service_request.id}\n"
                    f"- Service type: {service_type.name}\n"
                    f"- Price: {service_type.price_usd} USD\n"
                    f"- Status: {new_status.value}\n"
                    f"- Confirmed at: {service_request.updated.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"The service will be completed soon."
                ),
                "slack": (
                    f"✅ Service request confirmed\n\n"
                    f"ID: {service_request.id}\n"
                    f"User: {user.email}\n"
                    f"Service: {service_type.name}\n"
                    f"Status: {old_status.value} → {new_status.value}"
                ),
            },
            ServiceStatus.IN_PROGRESS: {
                "subject": f"Service in progress: {service_type.name}",
                "email": (
                    f"Hello, {user.first_name or user.email}!\n\n"
                    f"Your service request for '{service_type.name}' has been moved to 'In Progress' status.\n\n"
                    f"Request details:\n"
                    f"- Request ID: {service_request.id}\n"
                    f"- Service type: {service_type.name}\n"
                    f"- Status: {new_status.value}\n"
                    f"- Updated at: {service_request.updated.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"The service is in progress."
                ),
                "slack": (
                    f"🔄 Service in progress\n\n"
                    f"ID: {service_request.id}\n"
                    f"User: {user.email}\n"
                    f"Service: {service_type.name}\n"
                    f"Status: {old_status.value} → {new_status.value}"
                ),
            },
            ServiceStatus.COMPLETED: {
                "subject": f"Service completed: {service_type.name}",
                "email": (
                    f"Hello, {user.first_name or user.email}!\n\n"
                    f"Your service request for '{service_type.name}' has been successfully completed.\n\n"
                    f"Request details:\n"
                    f"- Request ID: {service_request.id}\n"
                    f"- Service type: {service_type.name}\n"
                    f"- Price: {service_type.price_usd} USD\n"
                    f"- Status: {new_status.value}\n"
                    f"- Completed at: {service_request.updated.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"Thank you for using our services!"
                ),
                "slack": (
                    f"✅ Service completed\n\n"
                    f"ID: {service_request.id}\n"
                    f"User: {user.email}\n"
                    f"Service: {service_type.name}\n"
                    f"Status: {old_status.value} → {new_status.value}"
                ),
            },
            ServiceStatus.CANCELLED: {
                "subject": f"Service request cancelled: {service_type.name}",
                "email": (
                    f"Hello, {user.first_name or user.email}!\n\n"
                    f"Your service request for '{service_type.name}' has been cancelled.\n\n"
                    f"Request details:\n"
                    f"- Request ID: {service_request.id}\n"
                    f"- Service type: {service_type.name}\n"
                    f"- Reserved amount: {service_request.reserved_amount} USD\n"
                    f"- Status: {new_status.value}\n"
                    f"- Cancelled at: {service_request.updated.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                ) + (
                    f"Reserved funds have been returned to your balance.\n"
                    if service_request.reserved_amount > Decimal("0")
                    else ""
                ) + (
                    f"\nYour current balance: "
                    f"{BalanceTransaction.objects.calculate_user_balance(user)} USD"
                ),
                "slack": (
                    f"❌ Service request cancelled\n\n"
                    f"ID: {service_request.id}\n"
                    f"User: {user.email}\n"
                    f"Service: {service_type.name}\n"
                    f"Status: {old_status.value} → {new_status.value}\n"
                    f"Refunded amount: {service_request.reserved_amount} USD"
                ),
            },
        }
        
        if new_status not in status_messages:
            logger.warning(
                f"No notification template for status change: {old_status} → {new_status}"
            )
            return
        
        message_data = status_messages[new_status]
        
        # Email to user
        NotificationService.send_email_notification(
            recipient_email=user.email,
            subject=message_data["subject"],
            message=message_data["email"],
        )
        
        # Slack to admin
        NotificationService.send_slack_notification(message_data["slack"])

    
    @staticmethod
    def notify_balance_topup(
        user,
        amount: Decimal,
        transaction: BalanceTransaction,
    ) -> None:
        """Send notifications when balance is topped up.
        """
        new_balance = BalanceTransaction.objects.calculate_user_balance(user)
        
        # Email to user
        email_subject = f"Balance topped up by {amount} USD"
        email_message = (
            f"Hello, {user.first_name or user.email}!\n\n"
            f"Your balance has been successfully topped up.\n\n"
            f"Transaction details:\n"
            f"- Transaction ID: {transaction.id}\n"
            f"- Top-up amount: {amount} USD\n"
            f"- Date: {transaction.created.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- Current balance: {new_balance} USD\n\n"
            f"Thank you for the top-up!"
        )
        NotificationService.send_email_notification(
            recipient_email=user.email,
            subject=email_subject,
            message=email_message,
        )
        
        # Slack to admin
        slack_message = (
            f"💰 Balance topped up\n\n"
            f"User: {user.email} ({user.first_name or ''} {user.last_name or ''})\n"
            f"Amount: {amount} USD\n"
            f"New balance: {new_balance} USD\n"
            f"Transaction ID: {transaction.id}\n"
            f"Date: {transaction.created.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        NotificationService.send_slack_notification(slack_message)

    
    @staticmethod
    def notify_insufficient_balance(
        user,
        service_type,
        required_amount: Decimal,
        current_balance: Decimal,
    ) -> None:
        """Send notifications when user has insufficient balance.
        """
        # Email to user
        email_subject = "Insufficient funds to create request"
        email_message = (
            f"Hello, {user.first_name or user.email}!\n\n"
            f"Unfortunately, you have insufficient funds in your balance to create a request for the service '{service_type.name}'.\n\n"
            f"Details:\n"
            f"- Service type: {service_type.name}\n"
            f"- Required amount: {required_amount} USD\n"
            f"- Your current balance: {current_balance} USD\n"
            f"- Shortfall: {required_amount - current_balance} USD\n\n"
            f"Please top up your balance to create the request."
        )
        NotificationService.send_email_notification(
            recipient_email=user.email,
            subject=email_subject,
            message=email_message,
        )
        
        # Slack to admin
        slack_message = (
            f"⚠️ Insufficient funds\n\n"
            f"User: {user.email} ({user.first_name or ''} {user.last_name or ''})\n"
            f"Service: {service_type.name}\n"
            f"Required: {required_amount} USD\n"
            f"Current balance: {current_balance} USD\n"
            f"Shortfall: {required_amount - current_balance} USD"
        )
        NotificationService.send_slack_notification(slack_message)

    
    @staticmethod
    def notify_payment_error(
        user,
        error_message: str,
        context: Optional[dict] = None,
    ) -> None:
        """Send notifications when payment error occurs.
        """
        # Slack to admin only
        slack_message = (
            f"🚨 Payment error\n\n"
            f"User: {user.email} ({user.first_name or ''} {user.last_name or ''})\n"
            f"Error: {error_message}\n"
        )
        if context:
            slack_message += "\nContext:\n"
            for key, value in context.items():
                slack_message += f"- {key}: {value}\n"
        
        NotificationService.send_slack_notification(slack_message)
