from rest_framework import status
from rest_framework.exceptions import APIException


class CustomAPIException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "A server error occurred."
    default_code = "error"

    def __init__(self, detail=None, code=None, status_code=None):
        self.status_code = status_code or code or self.status_code
        super().__init__(detail=detail, code=code)
