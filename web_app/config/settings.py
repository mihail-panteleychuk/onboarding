import os
from datetime import timedelta
from pathlib import Path

from config.environment import env

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

# Production or Development settings
IS_PRODUCTION = env.bool("IS_PRODUCTION")
IS_LOCAL = env.bool("IS_LOCAL")

ONBOARDING_ENABLED = env.bool("ONBOARDING_ENABLED")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True


ALLOWED_HOSTS = [
    "*",
    "localhost",
    "localhost:8001",
    "127.0.0.1",
    "0.0.0.0",
    "192.168.10.151",
    "192.168.10.151:8001",
    "inhouseapp.dataforest.tech",
]
INTERNAL_IPS = ALLOWED_HOSTS

AUTH_USER_MODEL = "user.User"

INSTALLED_APPS = [
    # unfold-admin
    "unfold", 
    "unfold.contrib.filters", 
    "unfold.contrib.forms",  
    "unfold.contrib.inlines", 
    "unfold.contrib.import_export",  
    "unfold.contrib.guardian",  
    "unfold.contrib.simple_history",  
    # django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 3rd party apps
    "modeltranslation",
    "corsheaders",
    "django_filters",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    # "django_cleanup.apps.CleanupConfig",
    "django.contrib.postgres",
    "drf_yasg",
    # "django-storages",    # need for connecting AWS S3 Bucket for static and media files
    # local apps
    "apps.core",
    "apps.admin_panel",
    "apps.authentication",
    "apps.user",
    "apps.subscription",
    "apps.dashboard",
    "apps.payments",
    "apps.billing",
]


SOCIAL_AUTH_AUTHENTICATION_BACKENDS = ("social_core.backends.apple.AppleIdAuth",)
# you may pass it through env and make it more securely
DJANGO_ADMIN_URL = env.str("DJANGO_ADMIN_URL", "api/admin/")

MIDDLEWARE = (
    "apps.core.middleware.DecryptingMiddleware",
    "apps.core.middleware.TraceRequestMiddleware",
    "apps.core.middleware.AppContextMiddleware",
    "apps.core.middleware.LoggingRulesMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "apps.core.middleware.CustomAuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.CustomJWTAuthenticationMiddleware",
    "apps.core.middleware.LangBasedOnUserSettingsMiddleware",
    "apps.core.middleware.RequestLogMiddleware",
)

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # "rest_framework_simplejwt.authentication.JWTAuthentication",
        "apps.core.auth.CustomJWTAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 20,
    "SEARCH_PARAM": "q",
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    "EXCEPTION_HANDLER": "apps.core.error_handler.rest_framework_custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=3),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "USER_AUTHENTICATION_RULE": "apps.core.auth.user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("apps.core.auth.CustomAccessToken",),
    "AUTH_HEADER_TYPES": ("JWT",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

CORS_ORIGIN_ALLOW_ALL = True
CORS_ORIGIN_WHITELIST = [
    "http://localhost:80",
    "http://localhost:3000",
    "https://inhouseapp.dataforest.tech",
    "http://inhouseapp.dataforest.tech",
]
CORS_PREFLIGHT_MAX_AGE = 600

ROOT_URLCONF = "config.urls"
AUTHENTICATION_BACKENDS = ["apps.core.auth.CustomModelAuthBackend"]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# defining file paths for log handlers
LOG_FILES = {
    #   HANDLER: file path
    "REQUESTS": "config/logs/REQUESTS/REQUESTS.log",
    "stripe": "config/logs/stripe/stripe.log",
}
# creating paths if not exists
for file_path in LOG_FILES.values():
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

# NOTE: this is AWS ALB trace ID header name. Change it if you're using a different trace ID header.
TRACE_ID_HEADER_NAME = env.str("TRACE_ID_HEADER_NAME", default="HTTP_X_AMZN_TRACE_ID")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{asctime} {message}",
            "style": "{",
        },
        "full": {
            "format": "%(asctime)-23s %(traceid)s %(userid)s %(levelname)-8s %(name)s %(funcName)s:%(lineno)-7d %(message)s",
            "style": "%",
        },
        "json": {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": (
                "%(asctime)s %(traceid)s %(userid)s %(levelname)s %(name)s %(filename)s %(funcName)s %(lineno)d %(message)s"  # noqa B950
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "filters": {
        "TrackingLogFilter": {
            # filter to add `traceid` to log records
            "()": "apps.core.utils.TrackingLogFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            # JSON is not-readable during local development
            "formatter": "full" if IS_LOCAL else "json",
            "filters": ("TrackingLogFilter",),
        },
        "stripe": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_FILES["stripe"],
            "maxBytes": 1024 * 1024 * 20,  # 20MB
            "backupCount": 7,
            "formatter": "simple",
        },
        "REQUESTS": {  # handler for middleware logging
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_FILES["REQUESTS"],
            "maxBytes": 1024 * 1024 * 20,  # 20MB
            "backupCount": 7,
            "formatter": "simple",
        },
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["console"],
            "level": env.str("LOG_LEVEL", default="INFO"),
        },
        "celery": {
            "handlers": ["console"],
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "propagate": False,
        },
        "stripe": {
            "handlers": ["stripe"],
            "level": "INFO",
            "propagate": True,
        },
        "REQUESTS": {
            "handlers": ["REQUESTS"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}


WSGI_APPLICATION = "config.wsgi.application"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
#
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": env.str("POSTGRES_DB", default="web_app"),
        "USER": env.str("POSTGRES_USER", default="postgres"),
        "PASSWORD": env.str("POSTGRES_PASSWORD", default="qwety12351994qwerty"),
        "HOST": env.str("POSTGRES_HOST", default="localhost"),
        "PORT": env.str("POSTGRES_PORT", default="5432"),
        "ATOMIC_REQUESTS": True,
    },
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 6,
        },
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# supported languages
LANGUAGES = (
    ("en", "English"),
    ("de", "German"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("it", "Italian"),
    ("nl", "Dutch"),
    ("pt", "Portuguese"),
    ("ru", "Russian"),
    ("zh-hans", "Chinese"),
)
LOCALE_PATHS = [BASE_DIR / "locale"]
# country detecting by request IP
GEOIP_PATH = BASE_DIR / "geoip2_country/GeoLite2-Country.mmdb"


STATIC_URL = "/api/static/"
STATIC_ROOT = BASE_DIR / "static"

MEDIA_URL = "/api/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Emails config
if IS_LOCAL:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.gmail.com"
    EMAIL_USE_TLS = True
    EMAIL_PORT = 587
    EMAIL_HOST_USER = env.str("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD")


# security settings
if not IS_LOCAL:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

DEFAULT_PASSWORD = env.str("DEFAULT_PASSWORD")

FRONT_DOMAIN = env.str("FRONT_DOMAIN")
API_DOMAIN = env.str("API_DOMAIN")
# PAYMENTS
STRIPE_PUBLISHABLE_KEY = env.str("STRIPE_PUBLISHABLE_KEY")
STRIPE_SECRET_KEY = env.str("STRIPE_SECRET_KEY")
STRIPE_ACCOUNT_ID = env.str("STRIPE_ACCOUNT_ID")
STRIPE_WEBHOOK_SECRET = env.str("STRIPE_WEBHOOK_SECRET", default="")

# https://inhouseapp.dataforest.tech/onboarding/checkout/payment/result
STRIPE_ORDER_SUCCESS_URL = f"https://{FRONT_DOMAIN}/onboarding/checkout/payment/"
STRIPE_UPDATE_SUCCESS_URL = f"https://{FRONT_DOMAIN}/settings/payment/"

# Hardcoded Stripe account bussiness profile address.
# In Production - is not used, and data is retrieved directly from STRIPE by STRIPE_ACCOUNT_ID
TEST_BUSSINESS_PROFILE = {
    "mcc": "5734",
    "name": "InHouse",
    "support_address": {
        "city": "Kiev",
        "country": "UA",
        "line1": "Solomyanska, 15A",
        "line2": None,
        "postal_code": "03058",
        "state": "місто Київ",
    },
    "support_email": "denis_m@dataforest.ai",
    "support_phone": "+380989592445",
    "support_url": None,
    "url": "https://inhouseapp.dataforest.tech/",
}

FERNET_SECRET_KEY = env.str(
    "FERNET_SECRET_KEY",
)  # at first time generate it using. `Fernet.generate_key()`

SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Auth Token JWT": {"type": "apiKey", "name": "Authorization", "in": "header"},
    },
}
SWAGGER_URL = env.str("SWAGGER_URL")


CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND", default="redis://redis:6379/1")
CELERY_ACCEPT_CONTENT = ["application/json", "json"]
CELERY_RESULT_SERIALIZER = CELERY_TASK_SERIALIZER = "json"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

# BILLING
BILLING_AUTO_CONFIRM_TIMEOUT = env.int("BILLING_AUTO_CONFIRM_TIMEOUT", default=120)  # 2 minutes in seconds

LOG_REQUESTS = env.bool("LOG_REQUESTS", default=True)  # to enable log-request middleware
LOG_ADMIN_REQUESTS = env.bool("LOG_ADMIN_REQUESTS", default=False)
LOG_API_REQUESTS = env.bool("LOG_API_REQUESTS", default=True)

CONST_INSTAGRAM_ACCOUNT = "https://www.instagram.com/dataforest_agency/"
CONST_COPYRIGHT_INFO = "Copyright © 2024 In-Home."
CONST_ADDRESS_INFO = "In Home address"



UNFOLD = {
    "SITE_TITLE": "IN_HOME_PROJECT",
    "SITE_HEADER": "IN_HOME_PROJECT",
    "SITE_URL": "/",
    "SITE_SYMBOL": "settings",  # symbol from icon set
    "SHOW_HISTORY": True, # show/hide "History" button, default: True
    "SHOW_VIEW_ON_SITE": True, # show/hide "View on site" button, default: True
    "SHOW_BACK_BUTTON": False, # show/hide "Back" button on changeform in header, default: False
    "STYLES": [],
    "SCRIPTS": [],
    "SIDEBAR": {
        "show_search": True,  # Search in applications and models names
        "show_all_applications": True,  # Dropdown with all applications and models
        "navigation": [
            {
                "title": _("Admin_Panel"),
                "separator": False,  # Top border
                "collapsible": False,  # Collapsible group of links
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",  # Supported icon set: https://fonts.google.com/icons
                        "link": reverse_lazy("admin:index"),
                    },
                    {
                        "title": _("Config variables"),
                        "icon": "settings", 
                        "link": reverse_lazy("admin:admin_panel_settings_changelist"),
                    },
                    {
                        "title": _("Emails White List"),
                        "icon": "alternate_email", 
                        "link": reverse_lazy("admin:admin_panel_emailswhitelist_changelist"),
                    },
                ],
            },
            {
                "title": _("Payments"),
                "separator": True,  
                "collapsible": True, 
                "items": [
                    {
                        "title": _("Cards"),
                        "icon": "credit_card",  
                        "link": reverse_lazy("admin:payments_card_changelist"),
                    },
                    {
                        "title": _("Billing address"),
                        "icon": "mintmark", 
                        "link": reverse_lazy("admin:payments_billingaddress_changelist"),
                    },
                    {
                        "title": _("Invoice line items"),
                        "icon": "payments", 
                        "link": reverse_lazy("admin:payments_invoicelineitem_changelist"),
                    },
                    {
                        "title": _("Invoices"),
                        "icon": "attach_money", 
                        "link": reverse_lazy("admin:payments_invoice_changelist"),
                    },
                ],
            },
            {
                "title": _("Subscription"),
                "separator": True,  
                "collapsible": True, 
                "items": [
                    {
                        "title": _("Plans"),
                        "icon": "article",  
                        "link": reverse_lazy("admin:subscription_plan_changelist"),
                    },
                    {
                        "title": _("Subscriptions"),
                        "icon": "loyalty", 
                        "link": reverse_lazy("admin:subscription_subscription_changelist"),
                    },
                ],
            },
            {
                "title": _("Authentication and Authorization"),
                "separator": True,  
                "collapsible": True, 
                "items": [
                    {
                        "title": _("Groups"),
                        "icon": "group",  
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
            {
                "title": _("Token Blacklist"),
                "separator": True,  
                "collapsible": True, 
                "items": [
                    {
                        "title": _("Blacklisted tokens"),
                        "icon": "scan_delete",  
                        "link": reverse_lazy("admin:token_blacklist_blacklistedtoken_changelist"),
                    },
                    {
                        "title": _("Blacklisted tokens"),
                        "icon": "key",  
                        "link": reverse_lazy("admin:token_blacklist_outstandingtoken_changelist"),
                    },
                ],
            },
            {
                "title": _("Users"),
                "separator": True,  
                "collapsible": True, 
                "items": [
                    {
                        "title": _("Users"),
                        "icon": "person",  
                        "link": reverse_lazy("admin:user_user_changelist"),
                    },
                    {
                        "title": _("Countries"),
                        "icon": "public",  
                        "link": reverse_lazy("admin:user_country_changelist"),
                    },
                ],
            },
        ],
    },
    
}
