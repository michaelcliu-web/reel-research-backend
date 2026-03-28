import os
import shutil
from api.models import (
    CustomUser,
    Thread,
    Generation,
    Prompt,
    PromptChoice,
)
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Deletes all all models except for superusers and deletes all files in /media"
    )

    def handle(self, *args, **kwargs):
        self.stdout.write("Deleting old data...")
        models = [
            CustomUser,
            Thread,
            Generation,
            Prompt,
            PromptChoice,
            Topic,
            Snippet,
        ]

        for m in models:
            self.stdout.write(f"Deleting {m.__name__}...")
            if m == CustomUser:
                m.objects.filter(is_superuser=False).delete()
            else:
                m.objects.all().delete()

        self.stdout.write("Deleting old /media/ data...")
        if os.path.exists("media/"):
            for root, dirs, files in os.walk("media/"):
                for f in files:
                    os.unlink(os.path.join(root, f))
                for d in dirs:
                    shutil.rmtree(os.path.join(root, d))
        self.stdout.write("Done deleting /media/ data!")
