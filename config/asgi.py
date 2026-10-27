import os
import environ
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env()

if env("ENVIRONMENT") == "LOCAL":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
elif env("ENVIRONMENT") == "PRODUCTION":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

django_asgi_app = get_asgi_application()

from api.routing import ws_urlpatterns
from clerkauth.middleware import TokenAuthMiddleware

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": TokenAuthMiddleware((URLRouter(ws_urlpatterns))),
    }
)
