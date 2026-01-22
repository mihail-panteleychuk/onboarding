"""Filters for billing app."""

from django_filters import rest_framework as rest_filter

from apps.billing.models import ServiceRequest


class ServiceRequestFilter(rest_filter.FilterSet):
    """Filter set for ServiceRequest model."""

    status = rest_filter.CharFilter(field_name="status", lookup_expr="exact")
    user = rest_filter.UUIDFilter(field_name="user__id", lookup_expr="exact")
    service_type = rest_filter.UUIDFilter(field_name="service_type__id", lookup_expr="exact")
    created = rest_filter.DateFromToRangeFilter(field_name="created")
    reserved_amount = rest_filter.NumberFilter(field_name="reserved_amount", lookup_expr="exact")
    reserved_amount_min = rest_filter.NumberFilter(field_name="reserved_amount", lookup_expr="gte")
    reserved_amount_max = rest_filter.NumberFilter(field_name="reserved_amount", lookup_expr="lte")

    class Meta:
        model = ServiceRequest
        fields = {
            "status": ["exact"],
            "reserved_amount": ["exact", "gte", "lte"],
        }
