from django.urls import path, include
from rest_framework import routers


from .views import (SubscriptionView, PlanViewSet)


Router = routers.DefaultRouter()
Router.register('plan', PlanViewSet)


urlpatterns = [
    path('', include(Router.urls)),
    path('<str:filter>/', SubscriptionView.as_view()),

]
