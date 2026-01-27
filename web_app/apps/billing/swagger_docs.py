"""Swagger documentation definitions for billing API endpoints."""

from drf_yasg import openapi

from apps.billing.serializers import (
    BalanceResponseSerializer,
    BalanceTopUpSerializer,
    BalanceTransactionSerializer,
    ChangeStatusSerializer,
    CreateServiceRequestSerializer,
    ServiceRequestSerializer,
    ServiceTypeSerializer,
)


# BalanceView.get
BALANCE_GET_DOCS = {
    "operation_description": (
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
    "manual_parameters": [
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
    "responses": {
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
    "tags": ["Balance"],
}


# ServiceTypeViewSet.list
SERVICE_TYPE_LIST_DOCS = {
    "operation_description": (
        "Get list of all available service types.\n\n"
        "Returns only active service types with their names and prices in USD.\n"
        "This endpoint is used to display available services when creating a new request."
    ),
    "responses": {
        200: ServiceTypeSerializer(many=True),
    },
    "tags": ["Service Types"],
}


# BalanceTransactionsView.get
BALANCE_TRANSACTIONS_GET_DOCS = {
    "operation_description": (
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
    "manual_parameters": [
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
    "responses": {
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
    "tags": ["Balance"],
}


# BalanceTransactionsExportView.get
BALANCE_TRANSACTIONS_EXPORT_GET_DOCS = {
    "operation_description": (
        "Export transactions to CSV file.\n\n"
        "**Access rules:**\n"
        "- **Admin:** can export transactions for any user (user_id parameter)\n"
        "- **User:** can export only own transactions\n\n"
        "**Parameters:**\n"
        "- `user_id`: User ID to export transactions for (admin only, optional for user)\n"
        "- `fields`: Comma-separated list of fields to include in CSV\n"
        "  Available fields: id, user_id, user_email, direction, kind, amount, service_request_id, external_id, created, updated\n"
        "  Default: id, user_email, direction, kind, amount, service_request_id, created\n"
        "- `ordering`: Sort by field (prefix '-' for descending, default: -created)\n\n"
        "**Response:**\n"
        "- CSV file with transaction data\n"
        "- Content-Type: text/csv\n"
        "- Filename: balance_transactions_YYYY-MM-DD_HH-MM-SS.csv"
    ),
    "manual_parameters": [
        openapi.Parameter(
            "user_id",
            openapi.IN_QUERY,
            description="User ID to export transactions for. Required for admin, optional for user (defaults to own ID).",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_UUID,
            required=False,
        ),
        openapi.Parameter(
            "fields",
            openapi.IN_QUERY,
            description="Comma-separated list of fields to include. Available: id, user_id, user_email, direction, kind, amount, service_request_id, external_id, created, updated",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            "ordering",
            openapi.IN_QUERY,
            description=(
                "Sort by field. Prefix with '-' for descending. "
                "Allowed fields: id, user_id, amount, direction, kind, "
                "service_request_id, external_id, created, updated. "
                "Examples: 'created', '-created', 'amount', '-amount'. "
                "Default: -created."
            ),
            type=openapi.TYPE_STRING,
            required=False,
        ),
    ],
    "responses": {
        200: openapi.Response(
            description="CSV file with transactions",
            schema=openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY),
        ),
        403: openapi.Response(description="Access denied. User cannot export other users' transactions."),
        404: openapi.Response(description="User not found."),
    },
    "tags": ["Balance"],
}


# BalanceTopUpView.post
BALANCE_TOPUP_POST_DOCS = {
    "operation_description": (
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
    "request_body": BalanceTopUpSerializer,
    "responses": {
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
    "tags": ["Balance"],
}


# ServiceRequestViewSet.create
SERVICE_REQUEST_CREATE_DOCS = {
    "operation_description": (
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
    "request_body": CreateServiceRequestSerializer,
    "responses": {
        201: ServiceRequestSerializer,
        400: openapi.Response(
            description="Validation error:\n"
            "- Service type not found or inactive\n"
            "- Insufficient balance\n"
            "- Invalid service_type_id format"
        ),
    },
    "tags": ["Service Requests"],
}


# ServiceRequestViewSet.list
SERVICE_REQUEST_LIST_DOCS = {
    "operation_description": (
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
    "manual_parameters": [
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
    "responses": {
        200: ServiceRequestSerializer(many=True),
    },
    "tags": ["Service Requests"],
}


# ServiceRequestViewSet.export
SERVICE_REQUEST_EXPORT_DOCS = {
    "operation_description": (
        "Export service requests to CSV.\n\n"
        "**Access:**\n"
        "- User: exports only their own requests (with all applied filters)\n"
        "- Admin: exports all matching requests\n\n"
        "**Filters & search:**\n"
        "Same query parameters as for the list endpoint `/api/billing/requests/`.\n"
        "- `search`: full-text search in user email, first_name, last_name, service type name (case-insensitive, by substring)\n"
        "- `status`: filter by status (pending, confirmed, in_progress, completed, cancelled)\n"
        "- `user`: filter by user ID (UUID)\n"
        "- `service_type`: filter by service type ID (UUID)\n"
        "- `created_after` / `created_before`: filter by creation date range (YYYY-MM-DD)\n"
        "- `reserved_amount`, `reserved_amount_min`, `reserved_amount_max`: filters by reserved amount\n"
        "- `ordering`: sort by field (prefix '-' for descending; same fields as in list endpoint)\n\n"
        "**Field selection:**\n"
        "- Use `fields` query parameter to control exported columns, e.g. "
        "`?fields=id,user_email,service_type_name,status,reserved_amount,created`.\n"
        "- If `fields` is not provided, a default set of columns is used.\n\n"
        "**Response:**\n"
        "- Content-Type: `text/csv`\n"
        "- Disposition: attachment with filename `service_requests.csv`."
    ),
    "manual_parameters": [
        openapi.Parameter(
            "search",
            openapi.IN_QUERY,
            description="Full-text search in user email, first_name, last_name, service type name (case-insensitive, by substring).",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            "status",
            openapi.IN_QUERY,
            description="Filter by status: pending, confirmed, in_progress, completed, cancelled.",
            type=openapi.TYPE_STRING,
            required=False,
            enum=["pending", "confirmed", "in_progress", "completed", "cancelled"],
        ),
        openapi.Parameter(
            "user",
            openapi.IN_QUERY,
            description="Filter by user ID (UUID). Only admins can see other users' requests; regular users will still see only their own.",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_UUID,
            required=False,
        ),
        openapi.Parameter(
            "service_type",
            openapi.IN_QUERY,
            description="Filter by service type ID (UUID).",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_UUID,
            required=False,
        ),
        openapi.Parameter(
            "created_after",
            openapi.IN_QUERY,
            description="Export requests created after this date (YYYY-MM-DD).",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_DATE,
            required=False,
        ),
        openapi.Parameter(
            "created_before",
            openapi.IN_QUERY,
            description="Export requests created before this date (YYYY-MM-DD).",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_DATE,
            required=False,
        ),
        openapi.Parameter(
            "reserved_amount",
            openapi.IN_QUERY,
            description="Export only requests with this exact reserved amount (decimal).",
            type=openapi.TYPE_NUMBER,
            required=False,
        ),
        openapi.Parameter(
            "reserved_amount_min",
            openapi.IN_QUERY,
            description="Export requests with reserved amount greater than or equal to this value (decimal).",
            type=openapi.TYPE_NUMBER,
            required=False,
        ),
        openapi.Parameter(
            "reserved_amount_max",
            openapi.IN_QUERY,
            description="Export requests with reserved amount less than or equal to this value (decimal).",
            type=openapi.TYPE_NUMBER,
            required=False,
        ),
        openapi.Parameter(
            "ordering",
            openapi.IN_QUERY,
            description=(
                "Sort by field. Prefix with '-' for descending order. "
                "Available fields: id, status, reserved_amount, created, updated, "
                "user__email, user__first_name, user__last_name, service_type__name, service_type__price_usd. "
                "Default: -created."
            ),
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            "fields",
            openapi.IN_QUERY,
            description=(
                "Comma-separated list of fields to include in CSV. "
                "Available fields: id, user_id, user_email, user_first_name, "
                "user_last_name, service_type_id, service_type_name, "
                "service_type_price_usd, status, reserved_amount, created, updated."
            ),
            type=openapi.TYPE_STRING,
            required=False,
        ),
    ],
    "responses": {
        200: openapi.Response(
            description="CSV file with exported service requests.",
            schema=openapi.Schema(type=openapi.TYPE_STRING),
        ),
        400: openapi.Response(description="Invalid fields parameter."),
    },
    "tags": ["Service Requests"],
}


# ServiceRequestViewSet.retrieve
SERVICE_REQUEST_RETRIEVE_DOCS = {
    "operation_description": (
        "Get detailed information about a specific service request.\n\n"
        "**Access:**\n"
        "- User: can view only their own requests\n"
        "- Admin: can view any request"
    ),
    "responses": {
        200: ServiceRequestSerializer,
        404: openapi.Response(description="Request not found or access denied."),
    },
    "tags": ["Service Requests"],
}


# ServiceRequestViewSet.cancel_request
SERVICE_REQUEST_CANCEL_DOCS = {
    "operation_description": (
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
    "responses": {
        200: ServiceRequestSerializer,
        400: openapi.Response(
            description="Request cannot be cancelled:\n"
            "- User trying to cancel non-pending request\n"
            "- User trying to cancel someone else's request"
        ),
        404: openapi.Response(description="Request not found."),
    },
    "tags": ["Service Requests"],
}


# ServiceRequestViewSet.change_status
SERVICE_REQUEST_CHANGE_STATUS_DOCS = {
    "operation_description": (
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
    "request_body": ChangeStatusSerializer,
    "responses": {
        200: ServiceRequestSerializer,
        400: openapi.Response(
            description="Invalid status transition:\n"
            "- Trying to transition from/to invalid status\n"
            "- Status transition not allowed by business rules"
        ),
        403: openapi.Response(description="Only admin can change status."),
        404: openapi.Response(description="Request not found."),
    },
    "tags": ["Service Requests"],
}
