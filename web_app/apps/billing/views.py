"""Views for billing API endpoints."""

from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import BalanceTransaction, ServiceRequest, ServiceType
from apps.billing.serializers import (
    BalanceResponseSerializer,
    BalanceTopUpSerializer,
    BalanceTransactionSerializer,
    CreateServiceRequestSerializer,
    ServiceRequestSerializer,
    ServiceTypeSerializer,
)
from apps.billing.services import BillingService
from apps.billing.stripe_service import create_checkout_session_for_topup
from apps.core.permissions import IsCustomAdminOrManagerUser
from apps.user.models import User


class ServiceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving service types."""

    queryset = ServiceType.objects.filter(is_active=True)
    serializer_class = ServiceTypeSerializer
    permission_classes = [permissions.IsAuthenticated]


class BalanceView(APIView):
    """View for getting user balance and transaction history."""

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get current user balance and transaction history.",
        responses={
            200: BalanceResponseSerializer,
        },
    )
    def get(self, request):
        """Get current balance and recent transactions."""
        user = request.user
        balance = BillingService.get_user_balance(user)
        
        transactions = BalanceTransaction.objects.for_user(user)[:20]
        
        serializer = BalanceResponseSerializer(
            {
                "balance": balance,
                "transactions": transactions,
            }
        )
        return Response(serializer.data)


class BalanceTopUpView(APIView):
    """View for creating Stripe Checkout Session for balance top-up."""

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create Stripe Checkout Session for balance top-up.",
        request_body=BalanceTopUpSerializer,
        responses={
            200: openapi.Response(
                description="Checkout session created successfully.",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "checkout_url": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="URL to redirect user for payment",
                        ),
                        "session_id": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Stripe Checkout Session ID",
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Validation error."),
        },
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
    """ViewSet for service requests."""

    serializer_class = ServiceRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        # Admin can see all requests, user can see only their own
        if user.role == User.UserRoleChoices.ADMIN:
            return ServiceRequest.objects.all().select_related("user", "service_type")
        return ServiceRequest.objects.filter(user=user).select_related("user", "service_type")

    @swagger_auto_schema(
        operation_description="Create a new service request.",
        request_body=CreateServiceRequestSerializer,
        responses={
            201: ServiceRequestSerializer,
            400: openapi.Response(description="Validation error or insufficient balance."),
        },
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
        operation_description="Cancel a service request (user can cancel only pending requests).",
        responses={
            200: ServiceRequestSerializer,
            400: openapi.Response(description="Request cannot be cancelled."),
        },
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_request(self, request, pk=None):
        """Cancel a service request."""
        service_request = self.get_object()
        
        try:
            BillingService.cancel_service_request_by_user(
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
