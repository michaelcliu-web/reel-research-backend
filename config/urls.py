from django.contrib import admin
from django.urls import path, re_path, include

from core.media import serve_media
from core.views import health_check

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("api/papers/", include("papers.urls")),
    re_path(r"^media/(?P<path>.*)$", serve_media),
]

handler404 = "core.views.page_not_found"
