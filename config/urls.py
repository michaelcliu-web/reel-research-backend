from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.http import JsonResponse
from django.views.static import serve


def health_check(request):
    """Health check endpoint for load balancers and container orchestration."""
    return JsonResponse({"status": "healthy", "service": "app-api"})


def page_not_found(request, exception=None):
    return JsonResponse({"error": "Not found"}, status=404)


urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("api/papers/", include("papers.urls")),
    path("accounts/", include("allauth.urls")),
    path("api/stripe/", include("payments.urls")),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

handler404 = "config.urls.page_not_found"
