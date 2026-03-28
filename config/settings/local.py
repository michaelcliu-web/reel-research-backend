import os
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env()

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
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

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    'django_extensions',
    # project apps
    "api",
    "payments",
    "papers",
    # third party apps
    "rest_framework",
    "rest_framework.authtoken",
    "django_cleanup.apps.CleanupConfig",
    "corsheaders",
    # AllAuth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Django OTP (2FA)
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    # channels
    "channels",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_jwt.authentication.JSONWebTokenAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.coreapi.AutoSchema",
}

JWT_AUTH = {
    "JWT_PAYLOAD_GET_USERNAME_HANDLER": "clerkauth.utils.jwt_get_username_from_payload_handler",
    "JWT_DECODE_HANDLER": "clerkauth.utils.jwt_decode_token",
    "JWT_ALGORITHM": "RS256",
    "JWT_AUTH_HEADER_PREFIX": "Bearer",
}

ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USERNAME_REQUIRED = False

ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.RemoteUserMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

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

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "django.contrib.auth.backends.RemoteUserBackend",
]

LOGIN_URL = "/login/"
AUTH_USER_MODEL = "api.CustomUser"
CORS_ALLOW_ALL_ORIGINS = True

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROOT_FRONTEND_URL = "http://localhost:3000/"
FRONTEND_URL = env("FRONTEND_URL", default=ROOT_FRONTEND_URL)

# Clerk
CLERK_FRONTEND_API = env("CLERK_FRONTEND_API")
CLERK_SECRET_KEY = env("CLERK_SECRET_KEY")

# Email
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'App <noreply@example.com>'
ADMIN_URL = 'http://localhost:8000/admin'

# Stripe
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET")

STRIPE_MONTHLY_PRICE_ID = env("STRIPE_MONTHLY_PRICE_ID", default="")
STRIPE_YEARLY_PRICE_ID = env("STRIPE_YEARLY_PRICE_ID", default="")
