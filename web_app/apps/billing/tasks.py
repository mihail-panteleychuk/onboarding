"""Celery tasks for billing operations."""

import logging
import random

from celery import shared_task
from django.db import transaction as db_transaction
from django.utils import timezone
from django.conf import settings

from apps.billing.constants import ServiceStatus
from apps.billing.models import BalanceTransaction, ServiceRequest
from apps.billing.notification_service import NotificationService
from apps.billing.services import BillingService
from apps.user.models import User

logger = logging.getLogger(__name__)


@shared_task
@db_transaction.atomic
def auto_confirm_service_request(service_request_id: str):
    """
    Auto-confirm or cancel service request after timeout.
    
    Randomly changes status from pending to either confirmed or cancelled.
    If cancelled, reserved funds are automatically refunded.
    """
    try:
        service_request = ServiceRequest.objects.select_for_update().get(id=service_request_id)
        
        # Check if request is still pending (might have been changed by admin)
        if service_request.status != ServiceStatus.PENDING:
            logger.info(
                f"Service request {service_request_id} is no longer pending "
                f"(current status: {service_request.status}). Skipping auto-confirmation."
            )
            return {"status": "skipped", "reason": "not_pending"}
        
        # Randomly choose confirmed or cancelled (50/50)
        new_status = random.choice([ServiceStatus.CONFIRMED, ServiceStatus.CANCELLED])
        
        logger.info(
            f"Auto-changing service request {service_request_id} status "
            f"from {service_request.status} to {new_status.value} "
            f"(random choice: {new_status.value})"
        )
        
        # Change status (this will handle refund if cancelled)
        BillingService.change_service_request_status(
            service_request=service_request,
            new_status=new_status.value,
        )
        
        logger.info(
            f"Successfully auto-changed service request {service_request_id} to {new_status}"
        )
        
        return {"status": "success", "new_status": new_status.value}
    
    except ServiceRequest.DoesNotExist:
        logger.error(f"Service request {service_request_id} not found")
        return {"status": "error", "reason": "not_found"}
    
    except Exception as e:
        logger.error(
            f"Error auto-confirming service request {service_request_id}: {str(e)}",
            exc_info=True,
        )
        return {"status": "error", "reason": str(e)}


@shared_task
@db_transaction.atomic
def process_stuck_pending_requests():
    """
    Periodic task to process stuck pending service requests.
    
    This task runs periodically (via Celery Beat) to find and process
    service requests that are stuck in pending status (e.g., created before
    Celery auto-confirmation was implemented, or if Celery task failed).
    
    Processes only requests older than BILLING_AUTO_CONFIRM_TIMEOUT seconds.
    """
    timeout_seconds = getattr(settings, "BILLING_AUTO_CONFIRM_TIMEOUT", 120)
    cutoff_time = timezone.now() - timezone.timedelta(seconds=timeout_seconds)
    
    # First, get the count without select_for_update
    count = ServiceRequest.objects.filter(
        status=ServiceStatus.PENDING,
        created__lt=cutoff_time,
    ).count()
    
    if count == 0:
        logger.info("No stuck pending requests found")
        return {"status": "success", "processed": 0}
    
    logger.info(f"Found {count} stuck pending request(s), processing...")
    
    # Now process each request in its own transaction
    processed = 0
    stuck_request_ids = list(
        ServiceRequest.objects.filter(
            status=ServiceStatus.PENDING,
            created__lt=cutoff_time,
        ).values_list("id", flat=True)
    )
    
    for request_id in stuck_request_ids:
        try:
            with db_transaction.atomic():
                request = ServiceRequest.objects.select_for_update().get(id=request_id)
                
                # Double-check status (might have been changed by another process)
                if request.status != ServiceStatus.PENDING:
                    logger.info(
                        f"Request {request_id} is no longer pending "
                        f"(status: {request.status}). Skipping."
                    )
                    continue
                
                # Randomly choose confirmed or cancelled (50/50)
                new_status = random.choice([ServiceStatus.CONFIRMED, ServiceStatus.CANCELLED])
                
                logger.info(
                    f"Processing stuck request {request.id}: "
                    f"{request.service_type.name} → {new_status.value} "
                    f"(random choice: {new_status.value})"
                )
                
                BillingService.change_service_request_status(
                    service_request=request,
                    new_status=new_status.value,
                )
                
                processed += 1
                
        except ServiceRequest.DoesNotExist:
            logger.warning(f"Request {request_id} not found (might have been deleted)")
        
        except Exception as e:
            logger.error(
                f"Error processing stuck request {request_id}: {str(e)}",
                exc_info=True,
            )
    
    logger.info(f"Processed {processed} out of {count} stuck request(s)")
    return {"status": "success", "processed": processed, "total": count}


@shared_task
def send_service_request_created_notification(service_request_id: str):
    """Send notifications when a service request is created."""
    try:
        service_request = ServiceRequest.objects.get(id=service_request_id)
        NotificationService.notify_service_request_created(service_request)
        return {"status": "success"}
    
    except ServiceRequest.DoesNotExist:
        logger.error(f"Service request {service_request_id} not found for notification")
        return {"status": "error", "reason": "not_found"}
    
    except Exception as e:
        logger.error(
            f"Error sending service request created notification: {str(e)}",
            exc_info=True,
        )
        return {"status": "error", "reason": str(e)}


@shared_task
def send_service_request_status_changed_notification(
    service_request_id: str,
    old_status: str,
    new_status: str,
):
    """Send notifications when service request status changes."""
    try:
        service_request = ServiceRequest.objects.get(id=service_request_id)
        old_status_enum = ServiceStatus(old_status)
        new_status_enum = ServiceStatus(new_status)
        NotificationService.notify_service_request_status_changed(
            service_request=service_request,
            old_status=old_status_enum,
            new_status=new_status_enum,
        )
        return {"status": "success"}
    
    except ServiceRequest.DoesNotExist:
        logger.error(f"Service request {service_request_id} not found for notification")
        return {"status": "error", "reason": "not_found"}
    
    except Exception as e:
        logger.error(
            f"Error sending status changed notification: {str(e)}",
            exc_info=True,
        )
        return {"status": "error", "reason": str(e)}


@shared_task
def send_balance_topup_notification(user_id: str, transaction_id: str):
    """Send notifications when balance is topped up."""
    try:
        user = User.objects.get(id=user_id)
        transaction = BalanceTransaction.objects.get(id=transaction_id)
        NotificationService.notify_balance_topup(
            user=user,
            amount=transaction.amount,
            transaction=transaction,
        )
        return {"status": "success"}
    
    except (User.DoesNotExist, BalanceTransaction.DoesNotExist) as e:
        logger.error(f"User or transaction not found for notification: {str(e)}")
        return {"status": "error", "reason": "not_found"}
    
    except Exception as e:
        logger.error(
            f"Error sending balance topup notification: {str(e)}",
            exc_info=True,
        )
        return {"status": "error", "reason": str(e)}


@shared_task
def send_insufficient_balance_notification(
    user_id: str,
    service_type_id: str,
    required_amount: str,
    current_balance: str,
):
    """Send notifications when user has insufficient balance."""
    try:
        from decimal import Decimal
        from apps.billing.models import ServiceType
        user = User.objects.get(id=user_id)
        service_type = ServiceType.objects.get(id=service_type_id)
        NotificationService.notify_insufficient_balance(
            user=user,
            service_type=service_type,
            required_amount=Decimal(required_amount),
            current_balance=Decimal(current_balance),
        )
        return {"status": "success"}
    
    except (User.DoesNotExist, ServiceType.DoesNotExist) as e:
        logger.error(f"User or service type not found for notification: {str(e)}")
        return {"status": "error", "reason": "not_found"}
    
    except Exception as e:
        logger.error(
            f"Error sending insufficient balance notification: {str(e)}",
            exc_info=True,
        )
        return {"status": "error", "reason": str(e)}


@shared_task
def send_payment_error_notification(user_id: str, error_message: str, context: dict = None):
    """Send notifications when payment error occurs."""
    try:
        user = User.objects.get(id=user_id)
        NotificationService.notify_payment_error(
            user=user,
            error_message=error_message,
            context=context,
        )
        return {"status": "success"}
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for notification")
        return {"status": "error", "reason": "not_found"}
    
    except Exception as e:
        logger.error(
            f"Error sending payment error notification: {str(e)}",
            exc_info=True,
        )
        return {"status": "error", "reason": str(e)}
