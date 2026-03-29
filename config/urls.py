from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.http import JsonResponse, FileResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.views.static import serve
import os
import re


def health_check(request):
    """Health check endpoint for load balancers and container orchestration."""
    return JsonResponse({"status": "healthy", "service": "app-api"})


def page_not_found(request, exception=None):
    return JsonResponse({"error": "Not found"}, status=404)


def serve_media(request, path):
    """Serve media files with HTTP Range request support so video seeking works."""
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.exists(full_path):
        return HttpResponseNotFound()

    file_size = os.path.getsize(full_path)
    range_header = request.META.get("HTTP_RANGE")

    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not match:
            return HttpResponseBadRequest()
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        f = open(full_path, "rb")
        f.seek(start)
        response = FileResponse(f, status=206)
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Content-Length"] = length
        response["Accept-Ranges"] = "bytes"
        return response

    response = FileResponse(open(full_path, "rb"))
    response["Content-Length"] = file_size
    response["Accept-Ranges"] = "bytes"
    return response


urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("api/papers/", include("papers.urls")),
    path("accounts/", include("allauth.urls")),
    path("api/stripe/", include("payments.urls")),
    re_path(r"^media/(?P<path>.*)$", serve_media),
]

handler404 = "config.urls.page_not_found"
