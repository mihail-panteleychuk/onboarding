"""Views for billing API endpoints."""

import csv
from datetime import datetime
from typing import Iterable, List

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as rest_filter
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.constants import ServiceStatus
from apps.billing.filters import ServiceRequestFilter
from apps.billing.models import BalanceTransaction, ServiceRequest, ServiceType


from apps.billing.serializers import (
    BalanceResponseSerializer,
    BalanceTopUpSerializer,
    BalanceTransactionSerializer,
    ChangeStatusSerializer,
    CreateServiceRequestSerializer,
    ServiceRequestSerializer,
    ServiceTypeSerializer,
    UserBalanceListSerializer,
    UserBalanceSerializer,
)
from apps.billing.services import BillingService
from apps.billing.stripe_service import StripeService
from apps.billing.tasks import send_payment_error_notification
from apps.billing.permissions import (
    CanAccessUserData,
    CanCancelServiceRequest,
    CanViewServiceRequest,
)
from apps.billing.swagger_docs import (
    BALANCE_GET_DOCS,
    BALANCE_TOPUP_POST_DOCS,
    BALANCE_TRANSACTIONS_EXPORT_GET_DOCS,
    BALANCE_TRANSACTIONS_GET_DOCS,
    SERVICE_REQUEST_CANCEL_DOCS,
    SERVICE_REQUEST_CHANGE_STATUS_DOCS,
    SERVICE_REQUEST_CREATE_DOCS,
    SERVICE_REQUEST_EXPORT_DOCS,
    SERVICE_REQUEST_LIST_DOCS,
    SERVICE_REQUEST_RETRIEVE_DOCS,
    SERVICE_TYPE_LIST_DOCS,
)
from apps.core.permissions import IsCustomAdminOrManagerUser
from apps.user.models import User


class CustomSearchFilter(filters.SearchFilter):
    """SearchFilter with custom search parameter name."""
    
    search_param = "search"


class StandardPagination(PageNumberPagination):
    """Standard pagination for billing endpoints."""
    
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class BillingBaseView(APIView):
    """Base view with common helper methods for billing operations."""
    
    def get_target_user(self, request):
        """Get target user based on user_id query parameter."""
        user_id_param = request.query_params.get("user_id")
        
        if user_id_param:
            return get_object_or_404(User, id=user_id_param)
        
        return request.user
    
    
    def get_active_users_queryset(self):
        """Get queryset of active users for admin operations."""
        return User.objects.filter(is_active=True, is_deleted=False).order_by("email")


class ServiceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing service types (read-only, no detail view needed)."""

    queryset = ServiceType.objects.filter(is_active=True)
    serializer_class = ServiceTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    
    @swagger_auto_schema(**SERVICE_TYPE_LIST_DOCS)
    def list(self, request, *args, **kwargs):
        """List all active service types."""
        return super().list(request, *args, **kwargs)
    
   
    @swagger_auto_schema(auto_schema=None)  # Hide from Swagger
    def retrieve(self, request, *args, **kwargs):
        """Disable detail view - only list is needed."""
        return Response(
            {"detail": "Service type detail view is not available. Use list endpoint."},
            status=status.HTTP_404_NOT_FOUND,
        )


class BalanceView(BillingBaseView):
    """View for getting user balance and transaction history.
    
    Access rules:
    - If user_id is not provided:
      * Admin: returns list of all users with their balances
      * User: returns own balance and transactions
    - If user_id is provided:
      * Admin: returns balance and transactions for specified user
      * User: returns own balance if user_id matches, otherwise 403 Forbidden
    """

    permission_classes = [permissions.IsAuthenticated, CanAccessUserData]
    pagination_class = StandardPagination

    
    @swagger_auto_schema(**BALANCE_GET_DOCS)
    def get(self, request):
        """Get balance and transactions based on user role and user_id parameter."""
        current_user = request.user
        user_id_param = request.query_params.get("user_id")

        # If user_id is not passed
        if not user_id_param:
            # The admin receives a list of all users with balances (with pagination)
            if current_user.role == User.UserRoleChoices.ADMIN:
                users = self.get_active_users_queryset()

                paginator = self.pagination_class()
                paginated_users = paginator.paginate_queryset(users, request)

                user_balances = BillingService.build_user_balance_list(paginated_users)

                return paginator.get_paginated_response(user_balances)

            balance = BillingService.get_user_balance(current_user)
            transactions = BalanceTransaction.objects.for_user(current_user)[:20]

            serializer = BalanceResponseSerializer(
                {
                    "balance": balance,
                    "transactions": transactions,
                }
            )
            return Response(serializer.data)

        # If user_id is passed (permission already checked access)
        target_user = self.get_target_user(request)

        # Admin can see the balance of any user, user can see only their own
        # (permission already verified that user can access this user_id)
        balance = BillingService.get_user_balance(target_user)
        transactions = BalanceTransaction.objects.for_user(target_user)[:20]

        serializer = BalanceResponseSerializer(
            {
                "balance": balance,
                "transactions": transactions,
            }
        )
        return Response(serializer.data)


class BalanceTransactionsView(BillingBaseView):
    """View for getting user transactions (admin only).
    
    Allows admins to view transactions for any user.
    Users can only view their own transactions.
    """

    permission_classes = [permissions.IsAuthenticated, CanAccessUserData]
    pagination_class = StandardPagination

    @swagger_auto_schema(**BALANCE_TRANSACTIONS_GET_DOCS)
    def get(self, request):
        """Get transactions for a user."""
        # Get target user (permission already checked access if user_id provided)
        target_user = self.get_target_user(request)
        
        # Get transactions
        transactions = BalanceTransaction.objects.for_user(target_user).order_by("-created")
        
        # Use pagination
        paginator = self.pagination_class()
        paginated_transactions = paginator.paginate_queryset(transactions, request)
        
        serializer = BalanceTransactionSerializer(paginated_transactions, many=True)
        return paginator.get_paginated_response(serializer.data)


class BalanceTransactionsExportView(BillingBaseView):
    """View for exporting transactions to CSV.    
    Separate view for export endpoint to avoid conflicts with GET method.
    """

    permission_classes = [permissions.IsAuthenticated, CanAccessUserData]

    @swagger_auto_schema(**BALANCE_TRANSACTIONS_EXPORT_GET_DOCS)
    def get(self, request):
        """Export transactions to CSV."""
        # Get target user (permission already checked access if user_id provided)
        target_user = self.get_target_user(request)

        # Prepare queryset, fields and mapping using service layer
        ordering_param = request.query_params.get("ordering")
        fields_param = request.query_params.get("fields")

        try:
            transactions, export_fields, available_fields = BillingService.prepare_transactions_export(
                target_user=target_user,
                ordering_param=ordering_param,
                fields_param=fields_param,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Create CSV response
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = f"balance_transactions_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        
        # Write BOM for Excel compatibility
        response.write('\ufeff')
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow(export_fields)
        
        # Write data rows
        for transaction in transactions:
            row = [available_fields[field](transaction) for field in export_fields]
            writer.writerow(row)
        
        return response


class BalanceTopUpView(APIView):
    """View for creating Stripe Checkout Session for balance top-up."""

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(**BALANCE_TOPUP_POST_DOCS)
    def post(self, request):
        """Create checkout session for balance top-up."""
        serializer = BalanceTopUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        amount = serializer.validated_data["amount"]
        
        try:
            checkout_data = StripeService.create_checkout_session_for_topup(
                user=request.user,
                amount=amount,
            )
            
            return Response(
                {
                    "checkout_url": checkout_data["url"],
                    "session_id": checkout_data["session_id"],
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            # Send notification about payment error
            send_payment_error_notification.delay(
                user_id=str(request.user.id),
                error_message=str(e),
                context={
                    "amount": str(amount),
                    "endpoint": "balance_topup",
                },
            )
            
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ServiceRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for service requests with full-text search, filtering, and sorting.
    
    Features:
    - Full-text search by user email, first_name, last_name, and service type name
    - Filtering by status, user, service_type, created date, reserved_amount
    - Sorting by all fields (id, status, reserved_amount, created, updated, user fields, service_type fields)
    - List, create, and cancel actions available
    - Update/delete operations are disabled (use cancel endpoint instead)
    """

    serializer_class = ServiceRequestSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewServiceRequest]
    pagination_class = StandardPagination
    http_method_names = ["get", "post"]  # Disable PUT, PATCH, DELETE
    filterset_class = ServiceRequestFilter
    
    filter_backends = (
        CustomSearchFilter,
        rest_filter.DjangoFilterBackend,
        filters.OrderingFilter,
    )
    
    # Full-text search fields (prefix $ means icontains)
    search_fields = [
        "$user__email",
        "$user__first_name",
        "$user__last_name",
        "$service_type__name",
    ]
    
    # Fields available for sorting
    ordering_fields = [
        "id",
        "status",
        "reserved_amount",
        "created",
        "updated",
        "user__email",
        "user__first_name",
        "user__last_name",
        "service_type__name",
        "service_type__price_usd",
    ]
    
    # Default ordering
    ordering = ["-created"]

    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        queryset = ServiceRequest.objects.select_related("user", "service_type")
        
        # Handle Swagger schema generation (AnonymousUser)
        if not user.is_authenticated or not hasattr(user, "role"):
            return queryset.none()
        
        # Admin can see all requests, user can see only their own
        if user.role == User.UserRoleChoices.ADMIN:
            return queryset.for_admin()
        
        return queryset.for_user(user)
        

    @swagger_auto_schema(**SERVICE_REQUEST_CREATE_DOCS)
    def create(self, request, *args, **kwargs):
        """Create a new service request."""
        serializer = CreateServiceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service_type = get_object_or_404(
            ServiceType,
            id=serializer.validated_data["service_type_id"],
        )
        
        try:
            service_request = BillingService.create_service_request(
                user=request.user,
                service_type=service_type,
            )
            
            response_serializer = ServiceRequestSerializer(service_request)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @swagger_auto_schema(**SERVICE_REQUEST_LIST_DOCS)
    def list(self, request, *args, **kwargs):
        """List service requests with search, filtering, and sorting."""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(**SERVICE_REQUEST_EXPORT_DOCS)
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """
        Export service requests to CSV.
        Uses the same filtering, search and ordering as the list endpoint.
        """

        fields_param = request.query_params.get("fields")

        # 1. Apply filters/search/ordering (without pagination)
        queryset = self.filter_queryset(self.get_queryset())

        # 2. Prepare fields and rows using service layer
        try:
            requested_fields, rows = BillingService.prepare_service_requests_export(
                queryset=queryset.iterator(chunk_size=500),
                fields_param=fields_param,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Prepare HTTP response as CSV
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="service_requests.csv"'

        writer = csv.writer(response)
        writer.writerow(requested_fields)

        # 4. Write data rows
        for row in rows:
            writer.writerow(row)

        return response

    @swagger_auto_schema(**SERVICE_REQUEST_RETRIEVE_DOCS)
    def retrieve(self, request, *args, **kwargs):
        """Get service request detail."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    
    def update(self, request, *args, **kwargs):
        """Disable update - status changes will be handled by admin endpoints."""
        return Response(
            {"detail": "Direct update is not allowed. Use cancel endpoint or admin status change."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    
    def partial_update(self, request, *args, **kwargs):
        """Disable partial update."""
        return self.update(request, *args, **kwargs)

    
    def destroy(self, request, *args, **kwargs):
        """Disable delete - use cancel endpoint instead."""
        return Response(
            {"detail": "Delete is not allowed. Use cancel endpoint to cancel requests."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @swagger_auto_schema(**SERVICE_REQUEST_CANCEL_DOCS)
    @action(detail=True, methods=["post"], url_path="cancel", permission_classes=[permissions.IsAuthenticated, CanCancelServiceRequest])
    def cancel_request(self, request, pk=None):
        """Cancel a service request."""
        service_request = self.get_object()
        
        try:
            BillingService.cancel_service_request(
                user=request.user,
                service_request=service_request,
            )
            
            response_serializer = ServiceRequestSerializer(service_request)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @swagger_auto_schema(**SERVICE_REQUEST_CHANGE_STATUS_DOCS)
    @action(detail=True, methods=["post"], url_path="change-status", permission_classes=[IsCustomAdminOrManagerUser])
    def change_status(self, request, pk=None):
        """Change service request status (admin only)."""
        service_request = self.get_object()
        serializer = ChangeStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data["status"]
        
        try:
            BillingService.change_service_request_status(
                service_request=service_request,
                new_status=new_status,
            )
            
            response_serializer = ServiceRequestSerializer(service_request)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
