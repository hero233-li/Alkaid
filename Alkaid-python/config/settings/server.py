from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *  # noqa: F403

if SECRET_KEY == "local-only-unsafe-secret-key":  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in the server environment")
if EXTERNAL_SYSTEM_MODE != "real":  # noqa: F405
    raise ImproperlyConfigured("server settings require EXTERNAL_SYSTEM_MODE=real")
if CELERY_TASK_ALWAYS_EAGER:  # noqa: F405
    raise ImproperlyConfigured("server settings forbid CELERY_TASK_ALWAYS_EAGER=true")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
