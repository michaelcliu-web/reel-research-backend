import uuid
from django.db import models
from django.conf import settings


class Paper(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="papers",
    )
    pdf_file = models.FileField(upload_to="papers/")
    title = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(max_length=50, default="uploaded")
    summary = models.TextField(blank=True, default="")
    narration_script = models.TextField(blank=True, default="")
    manim_code = models.TextField(blank=True, default="")
    key_takeaways = models.JSONField(blank=True, default=list)
    quiz = models.JSONField(blank=True, default=list)
    suggested_papers = models.JSONField(blank=True, default=list)
    video_path = models.CharField(max_length=500, blank=True, default="")
    audio_path = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title or 'Untitled'} ({self.status})"
