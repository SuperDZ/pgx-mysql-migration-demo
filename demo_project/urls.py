from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def healthz(_request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        return JsonResponse(
            {
                "status": "ok",
                "db_target": settings.DB_TARGET,
                "select_1": row[0] if row else None,
            }
        )
    except Exception as exc:
        return JsonResponse(
            {"status": "error", "db_target": settings.DB_TARGET, "error": str(exc)},
            status=500,
        )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("healthz/", healthz),
    path("demo/", include("banktel.urls")),
]
