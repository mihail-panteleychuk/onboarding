from django.urls import path, include
from rest_framework import routers


from .views import (SubscriptionCreateView, SubscriptionCancelView,
                    SubscriptionListView, SubscriptionUpdateView,
                    SubscriptionCancelRenewView, PlanViewSet)


Router = routers.DefaultRouter()
Router.register('plan', PlanViewSet)


urlpatterns = [
    path('', include(Router.urls)),
    path('', SubscriptionCreateView.as_view()),
    path('update/', SubscriptionUpdateView.as_view()),
    path('manage/<int:sub_id>/', SubscriptionCancelRenewView.as_view()),
    path('<int:category_id>/', SubscriptionCancelView.as_view()),
    path('<str:filter>/', SubscriptionListView.as_view()),

]
