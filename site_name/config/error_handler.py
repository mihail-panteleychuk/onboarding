from rest_framework.views import exception_handler


def rest_framework_custom_exception_handler(exc, context):
    # Call REST framework's default exception handler
    response = exception_handler(exc, context)
    resp = {}
    if response is not None:
        for key in response.data.keys():
            resp[key] = response.data[key]
            if isinstance(resp[key],list) and len(resp[key]) == 1:
                resp[key] = resp[key][0]
        response.data = {
            "message": resp,
            'status_code': response.status_code
        }

    return response
