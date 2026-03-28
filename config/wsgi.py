import os
from django.core.wsgi import get_wsgi_application
import environ

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env()

if env("ENVIRONMENT") == "LOCAL":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
elif env("ENVIRONMENT") == "PRODUCTION":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()
