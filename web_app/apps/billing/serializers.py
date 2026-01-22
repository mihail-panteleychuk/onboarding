"""Serializers for billing API endpoints."""

from decimal import Decimal

from rest_framework import serializers

from apps.billing.models import BalanceTransaction, ServiceRequest, ServiceType
from apps.billing.constants import ServiceStatus


class ServiceTypeSerializer(serializers.ModelSerializer):
    """Serializer for service type list/detail."""

    class Meta:
        model = ServiceType
        fields = ["id", "name", "price_usd", "is_active", "created", "updated"]
        read_only_fields = ["id", "created", "updated"]


class BalanceTransactionSerializer(serializers.ModelSerializer):
    """Serializer for balance transaction list/detail."""

    class Meta:
        model = BalanceTransaction
        fields = [
            "id",
            "direction",
            "kind",
            "amount",
            "service_request",
            "external_id",
            "created",
            "updated",
        ]
        read_only_fields = ["id", "created", "updated"]


class ServiceRequestSerializer(serializers.ModelSerializer):
    """Serializer for service request list/detail."""

    service_type = ServiceTypeSerializer(read_only=True)
    service_type_id = serializers.UUIDField(write_only=True, required=False)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    user_last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = ServiceRequest
        fields = [
            "id",
            "user",
            "user_email",
            "user_first_name",
            "user_last_name",
            "service_type",
            "service_type_id",
            "status",
            "reserved_amount",
            "created",
            "updated",
        ]
        read_only_fields = ["id", "user", "status", "reserved_amount", "created", "updated"]


class CreateServiceRequestSerializer(serializers.Serializer):
    """Serializer for creating a service request."""

    service_type_id = serializers.UUIDField(required=True)

    def validate_service_type_id(self, value):
        """Validate that service type exists and is active."""
        try:
            service_type = ServiceType.objects.get(id=value)
            
            if not service_type.is_active:
                raise serializers.ValidationError("Service type is not available.")
            
            return value
        
        except ServiceType.DoesNotExist:
            raise serializers.ValidationError("Service type not found.")


class ChangeStatusSerializer(serializers.Serializer):
    """Serializer for changing service request status (admin only)."""

    status = serializers.ChoiceField(choices=ServiceStatus.choices, required=True)


class BalanceTopUpSerializer(serializers.Serializer):
    """Serializer for creating a balance top-up checkout session."""

    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        min_value=Decimal("0.01"),
        help_text="Top-up amount in USD (minimum $0.01).",
    )

    def validate_amount(self, value):
        """Validate top-up amount."""
        
        if value <= Decimal("0"):
            raise serializers.ValidationError("Amount must be positive.")
        
        if value > Decimal("10000"):
            raise serializers.ValidationError("Amount cannot exceed $10,000.")
        
        return value


class BalanceResponseSerializer(serializers.Serializer):
    """Serializer for balance response."""

    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    transactions = BalanceTransactionSerializer(many=True, read_only=True)
