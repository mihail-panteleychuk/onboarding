import json
import logging
import traceback
import uuid
from collections import defaultdict
from datetime import datetime

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.middleware.locale import LocaleMiddleware
from django.utils import translation
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.app_context import app_context


class DecryptingMiddleware:
    """
    Middleware for decrypting encrypted request data.

    This middleware decrypts the request body if it is encrypted using Fernet encryption.
    """

    METHODS_FOR_DECRYPTING = ("POST", "PUT", "PATCH")

    def __init__(self, get_response):
        self.get_response = get_response

    def __decrypt(self, request):
        """
        Decrypt the request body if it is encrypted.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            HttpRequest: The modified HTTP request object with decrypted content, if applicable.
        """
        if (
            request.method in self.METHODS_FOR_DECRYPTING
            and request.body
            and request.headers["Content-Type"] == "application/json"
            and "encrypted" in request.body.decode("utf-8")
        ):
            fernet = Fernet(settings.FERNET_SECRET_KEY)
            try:
                body = fernet.decrypt(json.loads(request.body)["encrypted"].encode("utf-8"))
            except:  # noqa: E722
                body = request.body
            setattr(request, "_body", body)
        return request

    def __call__(self, request):
        """
        Process the incoming request.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            HttpResponse: The HTTP response object.
        """
        request = self.__decrypt(request)
        response = self.get_response(request)
        return response


class TraceRequestMiddleware:
    """
    Middleware to add trace_id to request object. Uses X-Request-ID header or generates UUID4.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_uuid = request.META.get(settings.TRACE_ID_HEADER_NAME) or uuid.uuid4().hex
        app_context.set(trace_id=request_uuid)
        return self.get_response(request)


class CustomAuthenticationMiddleware(AuthenticationMiddleware):
    """Class that wraps Django's AuthenticationMiddleware to set user_id in app_context"""

    def process_request(self, request):
        super().process_request(request)
        app_context.set(user=request.user, user_id=getattr(request.user, "id", None))


class CustomJWTAuthenticationMiddleware:
    """Authenticates user by JWT and applies to request and app_context"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # NOTE: if JWT is provided overrides the user from Django AuthenticationMiddleware
        auth_header = request.META.get("HTTP_AUTHORIZATION", None)
        if auth_header is not None:
            try:
                user, validated_token = JWTAuthentication().authenticate(request)
                if user and not user.is_anonymous:
                    request.user = user
                    app_context.set(user=user, user_id=user.id)
            except Exception:  # noqa
                pass
        return self.get_response(request)


class AppContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        app_context.set(request=request)
        try:
            return self.get_response(request)
        finally:
            # NOTE: that we should always clear `app_context`,
            # because Django can reuse the same thread for the next request.
            app_context.clear()


class LoggingRulesMiddleware:
    """
    Middleware to enable/disable logging based on request path.
    Check from app_context can be reused in other places.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logging_enabled = self.is_logging_request(request)
        app_context.set(logging_enabled=logging_enabled)
        return self.get_response(request)

    @staticmethod
    def is_logging_request(request) -> bool:
        request_path = request.get_full_path()
        if (
            # disable logging for non-api requests
            not request_path.startswith("/api/")
            # disable logging of healthcheck requests
            or request_path == "/api/heartbeat/"
            # disable logging for admin urls
            or settings.DJANGO_ADMIN_URL.strip("/") in request_path
            # disable logging for static and media files
            or request_path.startswith(settings.STATIC_URL)
            or request_path.startswith(settings.MEDIA_URL)
        ):
            return False

        return True  # allow all other requests logging


class LangBasedOnUserSettingsMiddleware(LocaleMiddleware):
    """
    Middleware to set language based on user settings.

    This middleware sets the language for the current request based on the user's language settings.
    If the user is authenticated and has a preferred language set, it uses that language.
    Otherwise, it falls back to the default language specified in the Django settings
    """

    def process_request(self, request):
        """
        Process the incoming request.

        Args:
            request: The HTTP request object.

        """
        if request.user and not request.user.is_anonymous:
            lang = request.user.language
        else:
            lang = settings.LANGUAGE_CODE
        translation.activate(lang)
        request.LANGUAGE_CODE = lang

    def process_response(self, request, response):
        """
        Process the outgoing response.
        """
        translation.deactivate()
        return response


class RequestLogMiddleware:
    """
    Middleware for logging incoming requests and outgoing responses.

    This middleware logs information about incoming requests and outgoing responses, including request details
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("REQUESTS")

        self.DEFAULT_LOG = {
            "timestamp": None,
            "message": {
                "level": "INFO",
                "request": None,
                "response": None,
                "exception": None,
            },
        }
        self.LOG_CONTENT = defaultdict(lambda: json.loads(json.dumps(self.DEFAULT_LOG)))

    def __call__(self, request):
        """
        Process the incoming request.

        Args:
            request: The HTTP request object.

        Returns:
            HttpResponse: The HTTP response object.

        """
        if app_context.logging_enabled:
            # TODO: split to started_at, finished_at and duration
            self.LOG_CONTENT[app_context.trace_id]["timestamp"] = str(datetime.now())
            user_uuid = (
                str(request.user.id) if request.user and request.user.is_authenticated else None
            )

            try:
                body = json.loads(request.body.decode("utf-8")) if request.body else {}
            except:  # noqa: E722
                body = {}
            log_request = {
                "remote_address": request.META.get("HTTP_X_FORWARDED_FOR"),
                "path": request.get_full_path(),
                "method": request.method,
                "body": body,
                "query_params": dict(request.GET) if request.GET else {},
                "user": user_uuid,
            }
            self.LOG_CONTENT[app_context.trace_id]["message"]["request"] = log_request

        # request passes on to controller
        response = self.get_response(request)

        # TODO: avoid using json.loads/json.dumps for performance reasons or use "ujson"
        if app_context.logging_enabled and response:
            try:
                resp_content = json.loads(response.content.decode("utf-8"))
            except:  # noqa: E722
                resp_content = str(getattr(response, "content", ""))

            log_response = {
                "status": getattr(response, "status_code", None),
                "content": resp_content,
            }
            # add runtime to our log_data
            self.LOG_CONTENT[app_context.trace_id]["message"]["response"] = log_response
            self.logger.info(
                json.dumps(self.LOG_CONTENT.pop(app_context.trace_id), ensure_ascii=False),
            )
        return response

    def process_exception(self, request, exception):
        """
        Process an exception that occurred during request processing.

        Args:
            request: The HTTP request object.
            exception: The exception object that was raised.

        Returns:
            None.

        """
        try:
            raise exception
        except Exception as e:
            if app_context.logging_enabled:
                self.LOG_CONTENT[app_context.trace_id]["message"] = {
                    "exception": {
                        "type": str(type(e)),
                        "traceback": traceback.format_exc(),
                    },
                    "level": "ERROR",
                }
        return None
