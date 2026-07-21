from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *  # noqa: F403

if SECRET_KEY == "local-only-unsafe-secret-key":  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in the server environment")
if EXTERNAL_SYSTEM_MODE != "real":  # noqa: F405
    raise ImproperlyConfigured("server settings require EXTERNAL_SYSTEM_MODE=real")
if CELERY_TASK_ALWAYS_EAGER:  # noqa: F405
    raise ImproperlyConfigured("server settings forbid CELERY_TASK_ALWAYS_EAGER=true")

required_external_settings = {
    "MOCK_PRODUCT_BASE_URL": MOCK_PRODUCT_BASE_URL,  # noqa: F405
    "APPLICATION_LINK_BASE_URL": APPLICATION_LINK_BASE_URL,  # noqa: F405
    "APPLICATION_LINK_API_TOKEN": APPLICATION_LINK_API_TOKEN,  # noqa: F405
    "BUSINESS_ACCESS_BASE_URL": BUSINESS_ACCESS_BASE_URL,  # noqa: F405
    "BUSINESS_ACCESS_API_TOKEN": BUSINESS_ACCESS_API_TOKEN,  # noqa: F405
    "VERIFICATION_APPROVAL_BASE_URL": VERIFICATION_APPROVAL_BASE_URL,  # noqa: F405
    "VERIFICATION_APPROVAL_API_TOKEN": VERIFICATION_APPROVAL_API_TOKEN,  # noqa: F405
}
missing_external_settings = [
    name for name, value in required_external_settings.items() if not str(value).strip()
]
if missing_external_settings:
    raise ImproperlyConfigured(
        "server external system settings are missing: " + ", ".join(missing_external_settings)
    )
if MOCK_FIXED_SYSTEM_TOKEN == "mock-fixed-token":  # noqa: F405
    raise ImproperlyConfigured("MOCK_FIXED_SYSTEM_TOKEN must be set for server mode")
if VERIFICATION_CONTEXT_SIGNING_KEY == "local-only-verification-context-key":  # noqa: F405
    raise ImproperlyConfigured("VERIFICATION_CONTEXT_SIGNING_KEY must be set for server mode")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
