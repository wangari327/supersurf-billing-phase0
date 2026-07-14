from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEVELOPMENT_SECRET_KEY = "dev-only-insecure-supersurf-key"
SUPPORTED_ENVIRONMENTS = {"DEVELOPMENT", "TEST", "LAB", "PRODUCTION"}
FALSE_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


def environment_label() -> str:
    configured = env("SUPERSURF_ENVIRONMENT", "DEVELOPMENT").upper()
    if configured not in SUPPORTED_ENVIRONMENTS:
        return "DEVELOPMENT"
    return configured


SUPERSURF_ENVIRONMENT = environment_label()
SUPERSURF_PUBLIC_DEPLOYMENT = env_bool("SUPERSURF_PUBLIC_DEPLOYMENT", default=False)
SECURE_PUBLIC_DEPLOYMENT = SUPERSURF_ENVIRONMENT == "PRODUCTION" or SUPERSURF_PUBLIC_DEPLOYMENT
SUPERSURF_STATICFILES_MANIFEST = env_bool("SUPERSURF_STATICFILES_MANIFEST", default=False)
MPESA_CALLBACK_TOKEN = env("MPESA_CALLBACK_TOKEN").strip()
MPESA_CALLBACK_BASE_URL = env(
    "MPESA_CALLBACK_BASE_URL",
    "https://sandbox-api.supersurf.co.ke",
).rstrip("/")


def validate_public_deployment_environment() -> None:
    if not SECURE_PUBLIC_DEPLOYMENT:
        return

    required = [
        "DJANGO_SECRET_KEY",
        "DATABASE_URL",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "DJANGO_DEBUG",
    ]
    if SUPERSURF_ENVIRONMENT == "LAB" and SUPERSURF_PUBLIC_DEPLOYMENT:
        required.append("MPESA_CALLBACK_TOKEN")
    missing = [name for name in required if not env(name).strip()]
    if missing:
        msg = "Missing required production setting(s): " + ", ".join(missing)
        raise ImproperlyConfigured(msg)

    if env("DJANGO_SECRET_KEY") == DEVELOPMENT_SECRET_KEY:
        msg = "DJANGO_SECRET_KEY must not use the development fallback in production."
        raise ImproperlyConfigured(msg)

    if env("DJANGO_DEBUG").strip().lower() not in FALSE_VALUES:
        msg = "DJANGO_DEBUG must be explicitly false in production."
        raise ImproperlyConfigured(msg)

    if (
        SUPERSURF_ENVIRONMENT == "LAB"
        and SUPERSURF_PUBLIC_DEPLOYMENT
        and len(MPESA_CALLBACK_TOKEN) < 32
    ):
        msg = "MPESA_CALLBACK_TOKEN must be at least 32 characters for public LAB."
        raise ImproperlyConfigured(msg)


validate_public_deployment_environment()


def database_config() -> dict[str, object]:
    database_url = env("DATABASE_URL")
    if not database_url:
        if SECURE_PUBLIC_DEPLOYMENT:
            msg = "DATABASE_URL must be supplied for public deployments."
            raise ImproperlyConfigured(msg)
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}

    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        msg = "DATABASE_URL must use PostgreSQL."
        raise ImproperlyConfigured(msg)

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }


SECRET_KEY = (
    env("DJANGO_SECRET_KEY")
    if SECURE_PUBLIC_DEPLOYMENT
    else env("DJANGO_SECRET_KEY", DEVELOPMENT_SECRET_KEY)
)
DEBUG = env_bool("DJANGO_DEBUG", default=not SECURE_PUBLIC_DEPLOYMENT)
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "" if SECURE_PUBLIC_DEPLOYMENT else "localhost,127.0.0.1",
)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "django_htmx",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "users",
    "core",
    "audit",
    "billing",
    "subscribers",
]

MIDDLEWARE = [
    "audit.middleware.CorrelationIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "axes.middleware.AxesMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "supersurf.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.environment_banner",
            ],
        },
    }
]

WSGI_APPLICATION = "supersurf.wsgi.application"

DATABASES = {"default": database_config()}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-ke"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_USE_MANIFEST = SECURE_PUBLIC_DEPLOYMENT or SUPERSURF_STATICFILES_MANIFEST
STATICFILES_STORAGE_BACKEND = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
    if STATICFILES_USE_MANIFEST
    else "whitenoise.storage.CompressedStaticFilesStorage"
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": STATICFILES_STORAGE_BACKEND,
    },
}
WHITENOISE_MANIFEST_STRICT = SECURE_PUBLIC_DEPLOYMENT

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = int(env("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_TEMPLATE = "registration/login.html"
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]

SESSION_COOKIE_AGE = int(env("SESSION_COOKIE_AGE", str(60 * 60 * 8)))
SESSION_SAVE_EVERY_REQUEST = True

BROKER_URL = env("BROKER_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = BROKER_URL
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER: tuple[str, str] | None

if SECURE_PUBLIC_DEPLOYMENT:
    DEBUG = False
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    if SUPERSURF_ENVIRONMENT == "PRODUCTION":
        SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000"))
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
    else:
        SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "0"))
        SECURE_HSTS_INCLUDE_SUBDOMAINS = False
        SECURE_HSTS_PRELOAD = False
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_PROXY_SSL_HEADER = None
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_secrets": {"()": "audit.logging.SecretRedactionFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["redact_secrets"],
        }
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}
