import json
import logging
import traceback
import uuid
from collections import defaultdict
from datetime import datetime

from cryptography.fernet import Fernet
from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation
from rest_framework_simplejwt.authentication import JWTAuthentication

from site_name.core.auth import CustomAccessToken


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


class LangBasedOnUserSettingsMiddleware(LocaleMiddleware):
    """
    Middleware to set language based on user settings.

    This middleware sets the language for the current request based on the user's language settings.
    If the user is authenticated and has a preferred language set, it uses that language.
    Otherwise, it falls back to the default language specified in the Django settings
    """

    @staticmethod
    def get_user_by_token(request):
        """
        Retrieve user information from the request token.

        Args:
            request: The HTTP request object.

        Returns:
            User: The authenticated user object if present, otherwise None.

        """
        header_token = request.META.get("HTTP_AUTHORIZATION", None)
        if header_token is not None:
            try:
                request.user = JWTAuthentication().authenticate(request)[0]
            except:  # noqa: E722
                request.user = None
            return request.user
        return None

    def process_request(self, request):
        """
        Process the incoming request.

        Args:
            request: The HTTP request object.

        """
        request.user = self.get_user_by_token(request)
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

    @staticmethod
    def get_user_id(request):
        """
        Retrieve user ID from the request token.

        Args:
            request: The HTTP request object.

        Returns:
            int: The user ID if present in the token, otherwise None.

        """
        header = request.META.get("HTTP_AUTHORIZATION")
        if header:
            header_token = header.split()[-1]
            token = CustomAccessToken(header_token)
            return token.get("user_id")
        return None

    def __call__(self, request):
        """
        Process the incoming request.

        Args:
            request: The HTTP request object.

        Returns:
            HttpResponse: The HTTP response object.

        """
        request_is_logging = bool(
            settings.DJANGO_ADMIN_URL not in request.get_full_path()
            and "api/" in request.get_full_path(),
        )
        request_uuid = uuid.uuid4().hex
        request.META["uuid"] = request_uuid

        if request_is_logging:
            self.LOG_CONTENT[request_uuid]["timestamp"] = str(datetime.now())
            try:
                user = self.get_user_id(request)
            except:  # noqa: E722
                user = None

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
                "user": user,
            }
            self.LOG_CONTENT[request.META.get("uuid")]["message"]["request"] = log_request

        # request passes on to controller
        response = self.get_response(request)
        if request_is_logging and response:
            try:
                resp_content = json.loads(response.content.decode("utf-8"))
            except:  # noqa: E722
                resp_content = str(getattr(response, "content", ""))

            log_response = {
                "status": getattr(response, "status_code", None),
                "content": resp_content,
            }
            # add runtime to our log_data
            self.LOG_CONTENT[request.META.get("uuid")]["message"]["response"] = log_response
            self.logger.info(
                json.dumps(self.LOG_CONTENT.pop(request.META.get("uuid")), ensure_ascii=False),
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
            if (
                settings.DJANGO_ADMIN_URL not in request.get_full_path()
                and "api/" in request.get_full_path()
            ):
                self.LOG_CONTENT[request.META["uuid"]]["message"] = {
                    "exception": {
                        "type": str(type(e)),
                        "traceback": traceback.format_exc(),
                    },
                    "level": "ERROR",
                }
        return None
