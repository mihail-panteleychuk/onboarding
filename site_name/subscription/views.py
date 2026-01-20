import datetime
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.functions import Now
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
# from payments import utils as payment_utils
from rest_framework import filters as rff
from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
# from user.models import BillingAddress, Country

from .constants import *
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer, SubscriptionCreateViewSerializer

# Create your views here.

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = None
    filter_backends = [rff.OrderingFilter]

    ordering = ['amount_products_per_week',]



class SubscriptionView(generics.RetrieveAPIView):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = (IsAuthenticated,)



    def get(self, request, filter, *args, **kwargs):
        """Get list of user current active  subscriptions"""
        if filter == 'active':
            subscription = request.user.subscriptions.filter(
                Q(next_payment_date__gt=Now(), next_payment_date__isnull=False) | Q(expire_date__gt=Now(), expire_date__isnull=False)).\
                filter(status__in=ACTIVE_STATUSES).order_by('-start_date').first()
            serializer = self.get_serializer(subscription).data if subscription else {}
        else:
            queryset = self.queryset.filter(user=request.user)
            queryset = request.user.subscriptions.all().order_by('-id')
            serializer = self.get_serializer(queryset, many=True).data
        return Response(serializer, status=status.HTTP_200_OK)

