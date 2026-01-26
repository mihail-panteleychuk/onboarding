from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="InHome API",
        default_version="v3",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)


urlpatterns = [
    path(settings.DJANGO_ADMIN_URL, admin.site.urls),  # django admin access
    path("api/", include("apps.core.urls")),
    path("api/auth/", include("apps.authentication.urls")),
    path("api/user/", include("apps.user.urls")),
    path("api/admin-panel/", include("apps.admin_panel.urls")),
    path("api/subscription/", include("apps.subscription.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/payments/", include("apps.payments.urls")),
    path("api/billing/", include("apps.billing.urls")),
    # path('api/demo/', include('demo.urls')),
    # path('api/portfolio/', include('portfolio.urls')),
]

if settings.SWAGGER_URL:
    urlpatterns.extend(
        [
            path(
                f"{settings.SWAGGER_URL}",
                schema_view.with_ui("swagger", cache_timeout=0),
                name="schema-swagger-ui",
            ),
            path(
                "api/api.json",
                schema_view.without_ui(cache_timeout=0),
                name="documentation",
            ),  # for export to postman collection
        ],
    )


# Раздача статических и медиа файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
