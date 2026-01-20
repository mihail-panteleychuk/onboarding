import gspread
import pandas as pd
import polib
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from apps.core.tasks import task_dummy, task_dummy_exception


@api_view(("GET",))
@renderer_classes((JSONRenderer,))
@permission_classes((AllowAny,))
def update_translates_back(request):
    pathes = [
        # pattern
        {"lang": "ru", "path": settings.BASE_DIR / "locale" / "ru" / "LC_MESSAGES" / "django.po"},
        {"lang": "de", "path": settings.BASE_DIR / "locale" / "de" / "LC_MESSAGES" / "django.po"},
        {"lang": "es", "path": settings.BASE_DIR / "locale" / "es" / "LC_MESSAGES" / "django.po"},
        {"lang": "it", "path": settings.BASE_DIR / "locale" / "it" / "LC_MESSAGES" / "django.po"},
        {"lang": "fr", "path": settings.BASE_DIR / "locale" / "fr" / "LC_MESSAGES" / "django.po"},
        {"lang": "nl", "path": settings.BASE_DIR / "locale" / "nl" / "LC_MESSAGES" / "django.po"},
        {"lang": "pt", "path": settings.BASE_DIR / "locale" / "pt" / "LC_MESSAGES" / "django.po"},
        {
            "lang": "zh-cn",
            "path": settings.BASE_DIR / "locale" / "zh-hans" / "LC_MESSAGES" / "django.po",
        },
    ]

    def read_gsheet():
        path = settings.BASE_DIR / "token.json"
        gc = gspread.service_account(filename=path)
        sh = gc.open_by_key(settings.TRANSLATION_GOOGLE_SHEET_ID).worksheet("Backend")
        worksheet = sh.get_all_values()
        return worksheet

    worksheet = read_gsheet()
    df = pd.DataFrame(columns=worksheet[0], data=worksheet[1:])
    df.drop_duplicates(subset=["code"], inplace=True)
    df.set_index("code", inplace=True)
    json_df = df.to_dict(orient="index")
    for po_file in pathes:
        try:
            read_file = polib.pofile(po_file["path"])
            # for entry in read_file.untranslated_entries():
            for entry in read_file:
                entry.msgstr = json_df.get(entry.msgid, {}).get(po_file["lang"], "")

            read_file.save(po_file["path"])
        except Exception as e:
            print(po_file["path"])
            print(e)
            return Response(
                {"message": {"detail": "Error while exporting translates", "error": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

    return Response({}, status=status.HTTP_202_ACCEPTED)


@api_view(("GET",))
@permission_classes((AllowAny,))
def heartbeat(request):
    return HttpResponse("OK", status=status.HTTP_200_OK)


@api_view(("POST",))
@permission_classes((AllowAny,))
def view_test_decrypt(request):
    return JsonResponse(dict(request.data), status=status.HTTP_200_OK)


@api_view(("POST", "GET"))
@permission_classes((AllowAny,))
def view_test_dummy_task(request):
    a = request.GET.get("a", 1)
    b = request.GET.get("b", 2)
    task_dummy.delay(a, b)
    return JsonResponse(
        {
            "msg": "success",
            "details": f"Schedule task with params a='{a}' and b='{b}' by user='{request.user.id}'",
        },
        status=status.HTTP_200_OK,
    )


@api_view(("POST", "GET"))
@permission_classes((AllowAny,))
def view_test_dummy_exception(request):
    task_dummy_exception.delay()
    return JsonResponse(
        {
            "msg": "success",
            "details": "Schedule task that will raise exception",
        },
        status=status.HTTP_200_OK,
    )
