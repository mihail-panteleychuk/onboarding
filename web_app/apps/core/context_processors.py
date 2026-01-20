from django.conf import settings


def const_info(request):
    return {
        "CONST_INSTAGRAM_ACCOUNT": settings.CONST_INSTAGRAM_ACCOUNT,
        "CONST_COPYRIGHT_INFO": settings.CONST_COPYRIGHT_INFO,
        "CONST_ADDRESS_INFO": settings.CONST_ADDRESS_INFO,
    }
