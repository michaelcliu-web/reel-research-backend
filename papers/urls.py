from django.urls import path
from papers.views import upload_paper

urlpatterns = [
    path("upload/", upload_paper, name="upload_paper"),
]
