from django.db.models import Q
from django.db.models.functions import Now
from rest_framework import filters as rff
from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.subscription.constants import PaymentStatus
from apps.subscription.models import Plan, Subscription
from apps.subscription.serializers import PlanSerializer, SubscriptionSerializer


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = None
    filter_backends = [rff.OrderingFilter]

    ordering = [
        "amount_products_per_week",
    ]


class SubscriptionView(generics.RetrieveAPIView):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = (IsAuthenticated,)

    def get(self, request, filter, *args, **kwargs):
        """Get list of user current active  subscriptions"""
        if filter == "active":
            subscription = (
                request.user.subscriptions.filter(
                    Q(next_payment_date__gt=Now(), next_payment_date__isnull=False)
                    | Q(expire_date__gt=Now(), expire_date__isnull=False),
                )
                .filter(status__in=PaymentStatus.active_statuses)
                .order_by("-start_date")
                .first()
            )
            serializer = self.get_serializer(subscription).data if subscription else {}
        else:
            queryset = request.user.subscriptions.all().order_by("-id")
            serializer = self.get_serializer(queryset, many=True).data
        return Response(serializer, status=status.HTTP_200_OK)
