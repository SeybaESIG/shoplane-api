import os

DEBUG = False

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()
]

CORS_ALLOW_CREDENTIALS = True

# Imported and extended rather than redefined to avoid silently dropping base settings.
from .base import REST_FRAMEWORK as _BASE_REST_FRAMEWORK  # noqa: E402

REST_FRAMEWORK = {
    **_BASE_REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/minute",
        "refresh": "20/minute",
        "user_read": "200/minute",
        "user_write": "60/minute",
    },
}
