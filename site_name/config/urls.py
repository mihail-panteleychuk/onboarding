"""dropship URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.authentication import JWTAuthentication
from .views import heartbeat


schema_view = get_schema_view(
   openapi.Info(
      title="InHome API",
      default_version='v3',
   ),
   public=True,
   permission_classes=(permissions.AllowAny, ),
   authentication_classes =[JWTAuthentication]

)


urlpatterns = [
    path('api/admin/', admin.site.urls),    # django admin access

    path('api/auth/', include('authentication.urls')),
    path('api/user/', include('user.urls')),
    path('api/admin-panel/', include('admin_panel.urls')),
    path('api/subscription/', include('subscription.urls')),
    # path('api/demo/', include('demo.urls')),
    # path('api/payments/', include('payments.urls')),
    # path('api/portfolio/', include('portfolio.urls')),
    # path('api/dashboard/', include('dashboard.urls')),

    path('api/heartbeat/', heartbeat),

]

if settings.IS_LOCAL:
    urlpatterns.extend([
        path('api/api.json', schema_view.without_ui(cache_timeout=0), name='documentation' ), # for export to postman collection
    ])


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

