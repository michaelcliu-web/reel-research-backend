from .base import *  # noqa: F401,F403

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".ngrok.io",
    ".ngrok-free.dev",
    ".ngrok-free.app",
]
CSRF_TRUSTED_ORIGINS = [
    "https://*.localhost",
    "https://*.127.0.0.1",
    "https://*.ngrok.io",
    "https://*.ngrok-free.dev",
    "https://*.ngrok-free.app",
]

INSTALLED_APPS = INSTALLED_APPS + ["django_extensions"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    },
}

CORS_ALLOW_ALL_ORIGINS = True

ROOT_FRONTEND_URL = "http://localhost:3000/"
FRONTEND_URL = env("FRONTEND_URL", default=ROOT_FRONTEND_URL)

# Email
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
ADMIN_URL = 'http://localhost:8000/admin'

X_FRAME_OPTIONS = "SAMEORIGIN"
