import json
import logging
import traceback
from datetime import datetime

from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation
from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework_simplejwt.tokens import AccessToken


class LangBasedOnUserSettingsMiddleware(LocaleMiddleware):

    def get_user_by_token(self, request):
        header_token = request.META.get('HTTP_AUTHORIZATION', None)
        if header_token is not None:
            try:
                request.user = JWTAuthentication().authenticate(request)[0]
            except:
                request.user = None
            return request.user
        return None

    def process_request(self, request):
        request.user = self.get_user_by_token(request)
        if request.user and not request.user.is_anonymous:
            lang = request.user.language
        else:
            lang = settings.LANGUAGE_CODE
        translation.activate(lang)
        request.LANGUAGE_CODE = lang

    def process_response(self, request, response):
        translation.deactivate()
        return response


class RequestLogMiddleware:
    """Request Logging Middleware."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("REQUESTS")
        self.LOG_CONTENT = {
            'timestamp': None,
            "message": {
                'level': 'INFO',
                'request': None,
                'response': None,
                'exception': None,
            }
        }

    def get_user_id(self, request):
        header = request.META.get('HTTP_AUTHORIZATION')
        if header:
            token = header.split()[-1]
            token = AccessToken(token)
            return token.get('user_id')
        return None

    def __call__(self, request):
        if not 'api/admin/' in request.get_full_path() and 'api/' in request.get_full_path():
            self.LOG_CONTENT['timestamp'] = str(datetime.now())
            try:
                user = self.get_user_id(request)
            except:
                user = None

            try:
                body = json.loads(request.body.decode("utf-8")) if request.body else dict()
            except:
                body = {}
            log_request = {
                "remote_address": request.META.get('HTTP_X_FORWARDED_FOR'),
                "path": request.get_full_path(),
                "method": request.method,
                "body": body,
                "query_params": dict(request.GET) if request.GET else dict(),
                'user': user,
            }
            self.LOG_CONTENT['message']['request'] = log_request

        # request passes on to controller
        response = self.get_response(request)
        if not 'api/admin/' in request.get_full_path() and response and 'api/' in request.get_full_path():
            try:
                resp_content = json.loads(response.content.decode("utf-8"))
            except:
                resp_content = str(getattr(response, 'content', ''))

            log_response = {
                'status': getattr(response, 'status_code', None),
                'content': resp_content
            }
            # add runtime to our log_data
            self.LOG_CONTENT['message']['response'] = log_response
            self.logger.info(json.dumps(self.LOG_CONTENT, ensure_ascii=False))

        return response

    # Log unhandled exceptions as well
    def process_exception(self, request, exception):
        try:
            raise exception
        except Exception as e:
            if not 'api/admin/' in request.get_full_path() and 'api/' in request.get_full_path():
                self.LOG_CONTENT['message']['exception'] = {
                    'type': str(type(e)),
                    'traceback': traceback.format_exc()
                }
                self.LOG_CONTENT['message']['level'] = 'ERROR'
                self.logger.error(json.dumps(self.LOG_CONTENT, ensure_ascii=False))
        return None
