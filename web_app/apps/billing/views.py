"""Views for billing API endpoints."""

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
from apps.billing.stripe_service import create_checkout_session_for_topup
from apps.core.permissions import IsCustomAdminOrManagerUser
from apps.user.models import User


class CustomSearchFilter(filters.SearchFilter):
    """SearchFilter with custom search parameter name."""
    
    search_param = "search"


class BalanceListPagination(PageNumberPagination):
    """Pagination for balance list (admin only)."""
    
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ServiceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing service types (read-only, no detail view needed)."""

    queryset = ServiceType.objects.filter(is_active=True)
    serializer_class = ServiceTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    
    @swagger_auto_schema(
        operation_description=(
            "Get list of all available service types.\n\n"
            "Returns only active service types with their names and prices in USD.\n"
            "This endpoint is used to display available services when creating a new request."
        ),
        responses={
            200: ServiceTypeSerializer(many=True),
        },
        tags=["Service Types"],
    )
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


class BalanceView(APIView):
    """View for getting user balance and transaction history.
    
    Access rules:
    - If user_id is not provided:
      * Admin: returns list of all users with their balances
      * User: returns own balance and transactions
    - If user_id is provided:
      * Admin: returns balance and transactions for specified user
      * User: returns own balance if user_id matches, otherwise 403 Forbidden
    """

    permission_classes = [permissions.IsAuthenticated]

    
    @swagger_auto_schema(
        operation_description=(
            "Get user balance and transaction history.\n\n"
            "**Access rules:**\n"
            "- **Without user_id parameter:**\n"
            "  - Admin: returns list of all users with their balances\n"
            "  - User: returns own balance and transactions\n\n"
            "- **With user_id parameter:**\n"
            "  - Admin: returns balance and transactions for specified user\n"
            "  - User: returns own balance if user_id matches, otherwise 403 Forbidden\n\n"
            "**Response format:**\n"
            "- Single user: balance + last 20 transactions\n"
            "- List (admin only): paginated list of users with their balances (no transactions in list)\n\n"
            "**Pagination (admin list only):**\n"
            "- Use `?page=1&page_size=20` to control pagination\n"
            "- Response includes: `count`, `next`, `previous`, `results`\n\n"
            "**Note:** Only admins can view other users' balances. Use `/api/billing/balance/transactions/?user_id=<uuid>` to view transactions."
        ),
        manual_parameters=[
            openapi.Parameter(
                "user_id",
                openapi.IN_QUERY,
                description="User ID to get balance for (admin only). If not provided, admin gets paginated list of all users, user gets own balance.",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=False,
            ),
            openapi.Parameter(
                "page",
                openapi.IN_QUERY,
                description="Page number for pagination (only for admin list view, default: 1)",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                "page_size",
                openapi.IN_QUERY,
                description="Number of items per page (only for admin list view, default: 20, max: 100)",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Balance information",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    oneOf=[
                        openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "balance": openapi.Schema(type=openapi.TYPE_NUMBER, description="Balance in USD"),
                                "transactions": openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_OBJECT),
                                    description="Last 20 transactions",
                                ),
                            },
                        ),
                        openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "count": openapi.Schema(type=openapi.TYPE_INTEGER, description="Total number of users"),
                                "next": openapi.Schema(type=openapi.TYPE_STRING, nullable=True, description="URL to next page"),
                                "previous": openapi.Schema(type=openapi.TYPE_STRING, nullable=True, description="URL to previous page"),
                                "results": openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "user_id": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID),
                                            "user_email": openapi.Schema(type=openapi.TYPE_STRING),
                                            "user_first_name": openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                                            "user_last_name": openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                                            "balance": openapi.Schema(type=openapi.TYPE_NUMBER),
                                        },
                                    ),
                                    description="List of users with their balances",
                                ),
                            },
                        ),
                    ],
                ),
            ),
            403: openapi.Response(description="Access denied. User cannot view other users' balances."),
            404: openapi.Response(description="User not found."),
        },
        tags=["Balance"],
    )
    def get(self, request):
        """Get balance and transactions based on user role and user_id parameter."""
        current_user = request.user
        user_id_param = request.query_params.get("user_id")
        
        # Authentication check
        if not current_user.is_authenticated or not hasattr(current_user, 'role'):
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        # If user_id is not passed
        if not user_id_param:
            # The admin receives a list of all users with balances (with pagination)
            if current_user.role == User.UserRoleChoices.ADMIN:
                users = User.objects.filter(is_active=True, is_deleted=False).order_by("email")                
                
                paginator = BalanceListPagination()
                paginated_users = paginator.paginate_queryset(users, request)
                
                user_balances = []
                
                for user in paginated_users:
                    balance = BillingService.get_user_balance(user)
                    user_balances.append({
                        "user_id": user.id,
                        "user_email": user.email,
                        "user_first_name": user.first_name,
                        "user_last_name": user.last_name,
                        "balance": balance,
                    })                
                
                return paginator.get_paginated_response(user_balances)            
            
            else:
                balance = BillingService.get_user_balance(current_user)
                transactions = BalanceTransaction.objects.for_user(current_user)[:20]
                
                serializer = BalanceResponseSerializer({
                    "balance": balance,
                    "transactions": transactions,
                })
                return Response(serializer.data)
        
        # If user_id is passed
        else:
            try:
                target_user = User.objects.get(id=user_id_param)
            
            except User.DoesNotExist:
                return Response(
                    {"detail": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # The admin can see the balance of any user.
            if hasattr(current_user, 'role') and current_user.role == User.UserRoleChoices.ADMIN:
                balance = BillingService.get_user_balance(target_user)
                transactions = BalanceTransaction.objects.for_user(target_user)[:20]
                
                serializer = BalanceResponseSerializer({
                    "balance": balance,
                    "transactions": transactions,
                })
                return Response(serializer.data)
            
            # The user can only see his own balance.
            else:
                if target_user.id != current_user.id:
                    return Response(
                        {"detail": "You do not have permission to view this user's balance."},
                        status=status.HTTP_403_FORBIDDEN,
                    )                
                
                balance = BillingService.get_user_balance(current_user)
                transactions = BalanceTransaction.objects.for_user(current_user)[:20]
                
                serializer = BalanceResponseSerializer({
                    "balance": balance,
                    "transactions": transactions,
                })
                return Response(serializer.data)


class BalanceTransactionsView(APIView):
    """View for getting user transactions (admin only).
    
    Allows admins to view transactions for any user.
    Users can only view their own transactions.
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            "Get transaction history for a user.\n\n"
            "**Access rules:**\n"
            "- **Admin:** can view transactions for any user (user_id required)\n"
            "- **User:** can view only own transactions (user_id must match own ID or be omitted)\n\n"
            "**Parameters:**\n"
            "- `user_id`: User ID to get transactions for (required for admin, optional for user)\n"
            "- `page`: Page number for pagination (default: 1)\n"
            "- `page_size`: Number of items per page (default: 20, max: 100)\n\n"
            "**Note:** Transactions are ordered by creation date (newest first)."
        ),
        manual_parameters=[
            openapi.Parameter(
                "user_id",
                openapi.IN_QUERY,
                description="User ID to get transactions for. Required for admin, optional for user (defaults to own ID).",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=False,
            ),
            openapi.Parameter(
                "page",
                openapi.IN_QUERY,
                description="Page number for pagination (default: 1)",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                "page_size",
                openapi.IN_QUERY,
                description="Number of items per page (default: 20, max: 100)",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Paginated list of transactions",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "count": openapi.Schema(type=openapi.TYPE_INTEGER, description="Total number of transactions"),
                        "next": openapi.Schema(type=openapi.TYPE_STRING, nullable=True, description="URL to next page"),
                        "previous": openapi.Schema(type=openapi.TYPE_STRING, nullable=True, description="URL to previous page"),
                        "results": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_OBJECT),
                            description="List of transactions",
                        ),
                    },
                ),
            ),
            403: openapi.Response(description="Access denied. User cannot view other users' transactions."),
            404: openapi.Response(description="User not found."),
        },
        tags=["Balance"],
    )
    def get(self, request):
        """Get transactions for a user."""
        current_user = request.user
        
        # Authentication check
        if not current_user.is_authenticated or not hasattr(current_user, 'role'):
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        user_id_param = request.query_params.get("user_id")
        
        # Defining the target user
        if user_id_param:
            try:
                target_user = User.objects.get(id=user_id_param)
            
            except User.DoesNotExist:
                return Response(
                    {"detail": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Checking access rights
            if not hasattr(current_user, 'role') or current_user.role != User.UserRoleChoices.ADMIN:
                # The user can only see their own transactions.
                if target_user.id != current_user.id:
                    return Response(
                        {"detail": "You do not have permission to view this user's transactions."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        else:
            # if user_id is not specified, the current user is used.
            target_user = current_user
        
        # Receiving transactions
        transactions = BalanceTransaction.objects.for_user(target_user).order_by("-created")
        
        # We use pagination
        paginator = BalanceListPagination()
        paginated_transactions = paginator.paginate_queryset(transactions, request)
        
        serializer = BalanceTransactionSerializer(paginated_transactions, many=True)
        return paginator.get_paginated_response(serializer.data)


class BalanceTopUpView(APIView):
    """View for creating Stripe Checkout Session for balance top-up."""

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            "Create Stripe Checkout Session for balance top-up.\n\n"
            "This endpoint initiates a payment flow through Stripe Checkout.\n"
            "After successful payment, the balance will be automatically updated via webhook.\n\n"
            "**Process:**\n"
            "1. User calls this endpoint with amount\n"
            "2. Stripe Checkout Session is created\n"
            "3. User is redirected to Stripe payment page\n"
            "4. After payment, webhook updates user balance\n\n"
            "**Minimum amount:** $0.01\n"
            "**Maximum amount:** $10,000"
        ),
        request_body=BalanceTopUpSerializer,
        responses={
            200: openapi.Response(
                description="Checkout session created successfully.",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "checkout_url": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="URL to redirect user to Stripe Checkout payment page",
                            example="https://checkout.stripe.com/pay/cs_test_...",
                        ),
                        "session_id": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Stripe Checkout Session ID (for tracking)",
                            example="cs_test_a1eNQEmNYehW6ZRYRCcMSzwwDRw1JDmIDdlVtFl8F2LYbqyiUM5NRpxnli",
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Validation error (invalid amount, etc.)."),
        },
        tags=["Balance"],
    )
    def post(self, request):
        """Create checkout session for balance top-up."""
        serializer = BalanceTopUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        amount = serializer.validated_data["amount"]
        
        try:
            checkout_data = create_checkout_session_for_topup(
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
    permission_classes = [permissions.IsAuthenticated]
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
        if not user.is_authenticated or not hasattr(user, 'role'):
            return queryset.none()
        
        # Admin can see all requests, user can see only their own
        if user.role == User.UserRoleChoices.ADMIN:
            return queryset.for_admin()
        
        return queryset.for_user(user)
        

    @swagger_auto_schema(
        operation_description=(
            "Create a new service request.\n\n"
            "**Process:**\n"
            "1. Validates that service type exists and is active\n"
            "2. Checks if user has sufficient balance\n"
            "3. Creates request with status 'pending'\n"
            "4. Reserves funds from user balance\n\n"
            "**Requirements:**\n"
            "- User must have sufficient balance (balance >= service price)\n"
            "- Service type must be active\n\n"
            "**Note:** Only regular users can create requests. Admins cannot create requests."
        ),
        request_body=CreateServiceRequestSerializer,
        responses={
            201: ServiceRequestSerializer,
            400: openapi.Response(
                description="Validation error:\n"
                "- Service type not found or inactive\n"
                "- Insufficient balance\n"
                "- Invalid service_type_id format"
            ),
        },
        tags=["Service Requests"],
    )
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

    @swagger_auto_schema(
        operation_description=(
            "Get list of service requests with full-text search, filtering, and sorting.\n\n"
            "**Access:**\n"
            "- User: sees only their own requests\n"
            "- Admin: sees all requests\n\n"
            "**Search & Filter Parameters:**\n"
            "- `search`: Full-text search in user email, first_name, last_name, service type name\n"
            "- `status`: Filter by status (pending, confirmed, in_progress, completed, cancelled)\n"
            "- `user`: Filter by user ID (UUID)\n"
            "- `service_type`: Filter by service type ID (UUID)\n"
            "- `created_after`: Filter requests created after date (YYYY-MM-DD)\n"
            "- `created_before`: Filter requests created before date (YYYY-MM-DD)\n"
            "- `reserved_amount`: Exact amount filter\n"
            "- `reserved_amount_min`: Minimum amount filter\n"
            "- `reserved_amount_max`: Maximum amount filter\n"
            "- `ordering`: Sort by field (prefix '-' for descending)\n\n"
            "**Available ordering fields:**\n"
            "id, status, reserved_amount, created, updated, user__email, user__first_name, "
            "user__last_name, service_type__name, service_type__price_usd\n\n"
            "**Default ordering:** -created (newest first)\n\n"
            "**Examples:**\n"
            "- `?search=john&status=pending`\n"
            "- `?ordering=-created&status=confirmed`\n"
            "- `?user=<uuid>&created_after=2026-01-01`"
        ),
        manual_parameters=[
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Full-text search in user email, first_name, last_name, service type name",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Filter by status: pending, confirmed, in_progress, completed, cancelled",
                type=openapi.TYPE_STRING,
                required=False,
                enum=["pending", "confirmed", "in_progress", "completed", "cancelled"],
            ),
            openapi.Parameter(
                "user",
                openapi.IN_QUERY,
                description="Filter by user ID (UUID)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=False,
            ),
            openapi.Parameter(
                "service_type",
                openapi.IN_QUERY,
                description="Filter by service type ID (UUID)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=False,
            ),
            openapi.Parameter(
                "created_after",
                openapi.IN_QUERY,
                description="Filter requests created after this date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                required=False,
            ),
            openapi.Parameter(
                "created_before",
                openapi.IN_QUERY,
                description="Filter requests created before this date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                required=False,
            ),
            openapi.Parameter(
                "reserved_amount",
                openapi.IN_QUERY,
                description="Filter by exact reserved amount (decimal)",
                type=openapi.TYPE_NUMBER,
                required=False,
            ),
            openapi.Parameter(
                "reserved_amount_min",
                openapi.IN_QUERY,
                description="Filter by minimum reserved amount (decimal)",
                type=openapi.TYPE_NUMBER,
                required=False,
            ),
            openapi.Parameter(
                "reserved_amount_max",
                openapi.IN_QUERY,
                description="Filter by maximum reserved amount (decimal)",
                type=openapi.TYPE_NUMBER,
                required=False,
            ),
            openapi.Parameter(
                "ordering",
                openapi.IN_QUERY,
                description=(
                    "Sort by field. Prefix with '-' for descending order.\n"
                    "Available fields: id, status, reserved_amount, created, updated, "
                    "user__email, user__first_name, user__last_name, service_type__name, service_type__price_usd"
                ),
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={
            200: ServiceRequestSerializer(many=True),
        },
        tags=["Service Requests"],
    )
    def list(self, request, *args, **kwargs):
        """List service requests with search, filtering, and sorting."""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description=(
            "Get detailed information about a specific service request.\n\n"
            "**Access:**\n"
            "- User: can view only their own requests\n"
            "- Admin: can view any request"
        ),
        responses={
            200: ServiceRequestSerializer,
            404: openapi.Response(description="Request not found or access denied."),
        },
        tags=["Service Requests"],
    )
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

    @swagger_auto_schema(
        operation_description=(
            "Cancel a service request.\n\n"
            "**User permissions:**\n"
            "- Can cancel only their own requests\n"
            "- Can cancel only requests with status 'pending'\n"
            "- Reserved funds are automatically refunded\n\n"
            "**Admin permissions:**\n"
            "- Can cancel any request (any status)\n"
            "- Reserved funds are automatically refunded if any\n\n"
            "**Result:**\n"
            "- Request status changes to 'cancelled'\n"
            "- Reserved funds are refunded to user balance"
        ),
        responses={
            200: ServiceRequestSerializer,
            400: openapi.Response(
                description="Request cannot be cancelled:\n"
                "- User trying to cancel non-pending request\n"
                "- User trying to cancel someone else's request"
            ),
            404: openapi.Response(description="Request not found."),
        },
        tags=["Service Requests"],
    )
    @action(detail=True, methods=["post"], url_path="cancel")
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

    @swagger_auto_schema(
        operation_description=(
            "Change service request status (admin only).\n\n"
            "**Valid status transitions:**\n"
            "- pending → confirmed, cancelled\n"
            "- confirmed → in_progress, cancelled\n"
            "- in_progress → completed, cancelled\n"
            "- completed → (no transitions allowed)\n"
            "- cancelled → (no transitions allowed)\n\n"
            "**Automatic actions:**\n"
            "- When changing to 'cancelled': reserved funds are refunded\n"
            "- When changing to 'confirmed': funds remain reserved (already reserved on creation)\n\n"
            "**Note:** Only admins can change request statuses."
        ),
        request_body=ChangeStatusSerializer,
        responses={
            200: ServiceRequestSerializer,
            400: openapi.Response(
                description="Invalid status transition:\n"
                "- Trying to transition from/to invalid status\n"
                "- Status transition not allowed by business rules"
            ),
            403: openapi.Response(description="Only admin can change status."),
            404: openapi.Response(description="Request not found."),
        },
        tags=["Service Requests"],
    )
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
