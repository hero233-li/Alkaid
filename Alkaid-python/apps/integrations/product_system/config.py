from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

MOCK_BASE_URLS = {
    "application_link": "https://mock-application-link.local",
    "business_access": "https://mock-business-access.local",
    "verification_approval": "https://mock-verification-approval.local",
}

REAL_SETTINGS = {
    "application_link": ("APPLICATION_LINK_BASE_URL", "APPLICATION_LINK_API_TOKEN"),
    "business_access": ("BUSINESS_ACCESS_BASE_URL", "BUSINESS_ACCESS_API_TOKEN"),
    "verification_approval": (
        "VERIFICATION_APPROVAL_BASE_URL",
        "VERIFICATION_APPROVAL_API_TOKEN",
    ),
}


def resolve_base_url(service: str, environment: str | None = None) -> str:
    del environment  # Current deployment exposes one base URL per product-system capability.
    if settings.EXTERNAL_SYSTEM_MODE == "mock":
        try:
            return MOCK_BASE_URLS[service]
        except KeyError:
            raise ImproperlyConfigured(f"未知产品外系统能力：{service}") from None
    try:
        setting_name, _ = REAL_SETTINGS[service]
    except KeyError:
        raise ImproperlyConfigured(f"未知产品外系统能力：{service}") from None
    value = getattr(settings, setting_name, "")
    if not value:
        raise ImproperlyConfigured(f"{setting_name} 未配置")
    return str(value)


def resolve_token(service: str) -> str | None:
    if settings.EXTERNAL_SYSTEM_MODE == "mock":
        return None
    _, setting_name = REAL_SETTINGS[service]
    return str(getattr(settings, setting_name, "") or "") or None
