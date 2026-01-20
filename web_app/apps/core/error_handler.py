from rest_framework.response import Response
from rest_framework.views import exception_handler


def rest_framework_custom_exception_handler(exc: Exception, context: dict) -> Response:
    """
    Custom exception handler for Django REST Framework.

    This function handles exceptions raised during API request processing and customizes the response format
    to include a consistent error message structure.

    Args:
        exc (Exception): The exception object raised during request processing.
        context (dict): The context information containing request and view details.

    Returns:
        Response: A customized response containing the error message and status code.

    """
    response = exception_handler(exc, context)
    resp = {}
    if response is not None:
        for key in response.data.keys():
            resp["detail"] = response.data[key]
            if isinstance(response.data[key], list):
                resp["detail"] = (
                    resp["detail"][0] if len(resp["detail"]) > 0 else "Something went wrong."
                )
            break
        response.data = {"message": resp, "status_code": response.status_code}
    return response
