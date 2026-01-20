import json
import logging
import traceback
import uuid
from collections import defaultdict
from datetime import datetime

from core.auth import CustomAccessToken
from django.conf import settings


class RequestLogMiddleware:
    """Request Logging Middleware."""

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

    def get_user_id(self, request):
        header = request.META.get("HTTP_AUTHORIZATION")
        if header:
            token = header.split()[-1]
            token = CustomAccessToken(token)
            return token.get("user_id")
        return None

    def __call__(self, request):
        request_is_logging = bool(
            settings.DJANGO_ADMIN_URL not in request.get_full_path()
            and "api/" in request.get_full_path()
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
                body = json.loads(request.body.decode("utf-8")) if request.body else dict()
            except:  # noqa: E722
                body = {}
            log_request = {
                "remote_address": request.META.get("HTTP_X_FORWARDED_FOR"),
                "path": request.get_full_path(),
                "method": request.method,
                "body": body,
                "query_params": dict(request.GET) if request.GET else dict(),
                "user": user,
            }
            self.LOG_CONTENT[request_uuid]["message"]["request"] = log_request

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
            self.LOG_CONTENT[request_uuid]["message"]["response"] = log_response
            self.logger.info(json.dumps(self.LOG_CONTENT.pop(request_uuid), ensure_ascii=False))
        return response

    # Log unhandled exceptions as well
    def process_exception(self, request, exception):
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
