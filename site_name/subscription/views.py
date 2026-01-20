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
from user.models import BillingAddress, Country

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

    ordering = ['amount_products_per_week']



class SubscriptionUpdateView(generics.CreateAPIView):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


    def post(self, request, *args, **kwargs):
        plan = request.data['plan']
        force = request.data.get('force')
        discount = request.data.get('discount_code')
        payment = request.data.get('payment')
        card = None
        #TODO revrite to ONE subscription (add sub_id as parameter)
        # for category_id, plan in plans.items():
        #     subscription = self.get_queryset().filter(category_id=category_id, status__in=[STATUS_PAID, STATUS_PAID_CANCELED, STATUS_TRIAL, STATUS_PENDING]).order_by('-start_date', '-id').first()
        #     plan = Plan.objects.get(pk=plan['id'])

        #     new_sub = payment_utils.update_subscription(subscription,
        #                                                 plan,
        #                                                 force_update=force,
        #                                                 coupon=discount,
        #                                                 intent_id=payment.get('intent_id') if force and payment else None)
        #     if isinstance(new_sub,dict) and "message" in new_sub:
        #         errors.append(new_sub)
        #         continue


        #     if force:
        #         old_status = subscription.status
        #         if old_status == STATUS_TRIAL:
        #             subscription.expire_date = datetime.fromtimestamp(new_sub.trial_end, tz=timezone.utc)

        #         else:
        #             subscription.expire_date = datetime.fromtimestamp(new_sub.current_term_start, tz=timezone.utc)
        #             subscription.next_payment_date = None
        #         subscription.status = STATUS_CANCELED
        #         subscription.save()
        #         new_sub_obj = Subscription(
        #             payment_subscription_id=new_sub.id,
        #             user=self.request.user,
        #             category=subscription.category,
        #             plan=plan,
        #             start_date=datetime.fromtimestamp(new_sub.current_term_start or new_sub.next_billing_at, tz=timezone.utc),
        #             next_payment_date=datetime.fromtimestamp(new_sub.current_term_end or new_sub.next_billing_at, tz=timezone.utc),
        #             status=old_status if old_status != STATUS_TRIAL else get_status(new_sub.status),
        #             scheduled_plan=None,
        #             discount=None
        #         )
        #         new_sub_obj.save()
        #         drops_to_remove = self.request.user.user_drops.filter(category=subscription.category, plan=subscription.plan, drop_date__gt=now())
        #         new_drops = Drop.objects.filter(category=subscription.category,
        #                                         plan=new_sub_obj.plan,
        #                                         drop_date__gte=now(),
        #                                         drop_date__lte=new_sub_obj.next_payment_date)

        #         self.request.user.user_drops.remove(*drops_to_remove)
        #         self.request.user.user_drops.add(*new_drops)
        #         del new_drops, drops_to_remove

        #         res = self.get_serializer(new_sub_obj).data
        #         responses.append(res)
        #         # errors.append({})

        #     else:
        #         #! notify frontenders that STATUS_SCHEDULED is not using anymore. they need to use field `scheduled_plan`
        #         subscription.scheduled_plan = plan
        #         subscription.save()

        #         res = self.get_serializer(subscription).data
        #         responses.append(res)
        #         # errors.append({})
        # resp = {"subscriptions": responses, "errors": errors}
        # if card:
        #     resp.update(card)
        return Response({}, status = status.HTTP_200_OK)

class SubscriptionCreateView(generics.CreateAPIView):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionCreateViewSerializer
    permission_classes = (IsAuthenticated,)


    def post(self, request, *args, **kwargs):
        """Subscribe user to specific plans and categories"""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status = status.HTTP_400_BAD_REQUEST)
        data = serializer.data

        discount_id = data.get('discount_code')
        plan_id = data['plan']
        payment = data.get('payment')

        # handle if user confirm emails receiving
        email_subscribed = data['email_subscribed']
        user = request.user
        user.email_subscribed = email_subscribed

        if BillingAddress.objects.filter(user=user).count() == 0 and data.get('billing_address'):
            data['billing_address']['country'] = Country.objects.filter(id=data['billing_address']['country']).first()
            data['billing_address']['phone'] = data['phone'].replace(' ', '') if data.get('phone') else None
            data['billing_address']['phone_code'] = Country.objects.filter(id=data.get('country_code')).first() if data.get('country_code') else None
            billing = BillingAddress(**data['billing_address'], user=user)
            billing.save()

        elif data.get('billing_address'):
            data['billing_address']['country'] = Country.objects.filter(id=data['billing_address']['country']).first()
            data['billing_address']['phone'] = data['phone'].replace(' ', '') if data.get('phone') else None
            data['billing_address']['phone_code'] = Country.objects.filter(id=data.get('country_code')).first() if data.get('country_code') else None
            billing = BillingAddress.objects.filter(user=user).update(**data['billing_address'])
            BillingAddress.objects.filter(user=user).first().save()

        # # created_sub = payment_utils.create_subscriptions_for_user(self.user,
        # #                                                            plan_id,
        # #                                                            discount_id,
        # #                                                            intent_id = payment.get('intent_id') if payment else None)
        # # if isinstance(created_sub, dict) and "message" in created_sub:
        # #     _status = status.HTTP_400_BAD_REQUEST
        # #     return Response(created_sub, status=_status)
        # # messages = {'subscription': self.get_serializer(created_sub).data}
        user.onboarding_finished = True
        user.save()

        messages = {'subscription': {}}
        return Response(messages, status=status.HTTP_201_CREATED)


class SubscriptionListView(generics.RetrieveAPIView):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = (IsAuthenticated,)

    def __get_free_access_sub(self):

        plan = Plan.objects.filter(status=True).order_by('-amount_products_per_week').first()
        start_date = now() + timedelta(days=1)
        end_date = now() + timedelta(days=30)

        resp = {
            "id": 1,
            "plan": PlanSerializer(plan, context={'request': self.request}).data,
            "active": True,
            "start_date":  start_date.strftime('%Y-%m-%d %H:%M:%S'),
            "expire_date": None,
            "payment_status": {
                "id": 1,
                "name": "Paid"
            },
            "next_payment_date": end_date.strftime('%Y-%m-%d %H:%M:%S'),
            "scheduled_plan": None
        }

        return Response(resp, status=status.HTTP_200_OK)


    def get(self, request, filter, *args, **kwargs):
        """Get list of user current active  subscriptions"""
        if self.request.user.role == get_user_model().FREE_ACCESS:
            return self.__get_free_access_sub()
        if filter == 'active':
            subscription = request.user.subscriptions.filter(
                Q(next_payment_date__gt=Now(), next_payment_date__isnull=False) | Q(expire_date__gt=Now(), expire_date__isnull=False)).\
                filter(status__in=[STATUS_PAID, STATUS_PAID_CANCELED]).order_by('-id').first()
            serializer = self.get_serializer(subscription)
        else:
            queryset = self.queryset.filter(user=request.user)
            queryset = request.user.subscriptions.all().order_by('-id')
            serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SubscriptionCancelView(generics.DestroyAPIView, generics.CreateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = SubscriptionSerializer

    def delete(self, request, subscription_id, *args, **kwargs):
        """Cancel user scheduled subscriptions"""

        subscription = get_object_or_404(request.user.subscriptions, pk=subscription_id)

        old_plan = subscription.scheduled_plan
        subscription.scheduled_plan=None
        subscription.save()

        # #  payment_utils.remove_scheduled_changes(subscription)

        response = {
            'status': 'Success',
            'message': 'Subscription is canceled',
            "subscription": self.get_serializer(subscription).data,
            "old_schedule": PlanSerializer(old_plan).data
        }

        return Response(response, status=status.HTTP_200_OK)

    def post(self, request, subscription_id, *args, **kwargs):
        """Restore user scheduled(canceled) subscriptions"""

        subscription = get_object_or_404(request.user.subscriptions, pk=subscription_id)

        plan_data = self.request.data.get("old_schedule")
        plan = get_object_or_404(Plan.objects.filter(status=True), pk=plan_data['id'])


        # # payment_utils.update_subscription(subscription, plan)
        subscription.scheduled_plan = plan
        subscription.save()

        response = {
            'status': 'Success',
            'message': 'Subscription is scheduled',
            "subscription": self.get_serializer(subscription).data,
        }

        return Response(response, status=status.HTTP_200_OK)


class SubscriptionCancelRenewView(generics.DestroyAPIView, generics.CreateAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Subscription.objects.all()

    def delete(self, request, sub_id, *args, **kwargs):
        """Downgrade sub to Free Plan"""

        sub = get_object_or_404(request.user.subscriptions, pk=sub_id)
        plan = get_object_or_404(Plan.objects.filter(status=True), is_trial=True)


        # # chargebee_sub = payment_utils.update_subscription(sub, plan, force_update=False)
        # # if isinstance(chargebee_sub, dict) and "message" in chargebee_sub:
        # #     return Response(chargebee_sub, status=status.HTTP_400_BAD_REQUEST)
        # # sub.expire_date = datetime.fromtimestamp(chargebee_sub.current_term_end, tz=timezone.utc)

        sub.status = STATUS_PAID_CANCELED
        sub.expire_date = self.next_payment_date
        sub.scheduled_plan = plan
        sub.next_payment_date = None
        sub.save()


        response = {
            'status': 'Success',
            'message': _('Plan cancellation scheduled!'),
            'subscription': self.get_serializer(sub).data
        }

        return Response(response, status=status.HTTP_200_OK)

    def post(self, request, sub_id, *args, **kwargs):
        """Cancel user subscription downgrading to Free Plan"""
        sub = get_object_or_404(request.user.subscriptions, pk=sub_id)

        # # chargebee_sub = payment_utils.remove_scheduled_changes(sub)
        # # if isinstance(chargebee_sub, dict) and "message" in chargebee_sub:
        # #     return Response(chargebee_sub, status=status.HTTP_400_BAD_REQUEST)
        # # sub.next_payment_date = datetime.fromtimestamp(chargebee_sub.next_billing_at, tz=timezone.utc)

        sub.status = STATUS_PAID
        sub.expire_date = None
        sub.scheduled_plan = None
        sub.next_payment_date = now() + timedelta(days=30)
        sub.save()


        response = {
            'status': 'Success',
            'message': _('Schedule Canceled!'),
            'subscription': self.get_serializer(sub).data
        }

        return Response(response, status=status.HTTP_200_OK)



