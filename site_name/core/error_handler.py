from rest_framework.views import exception_handler


def rest_framework_custom_exception_handler(exc, context):
    # Call REST framework's default exception handler
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
