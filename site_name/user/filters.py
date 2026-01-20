from django_filters import rest_framework as rest_filter

from .models import User


class NumberInFilter(rest_filter.BaseInFilter, rest_filter.NumberFilter):
    pass


class UserFilter(rest_filter.FilterSet):
    created = rest_filter.DateFromToRangeFilter(field_name="created")

    class Meta:
        model = User
        fields = {
            "email": ["exact", "iexact"],
            "first_name": ["exact", "iexact"],
            "last_name": ["exact", "iexact"],
            "created": ["exact"],
        }
