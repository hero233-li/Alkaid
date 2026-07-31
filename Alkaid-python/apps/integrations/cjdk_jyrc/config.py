import json
import os
from collections.abc import Mapping

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def resolve_base_url(environment: str) -> str:
    normalized = environment.strip().lower()
    if not normalized:
        raise ImproperlyConfigured("产品申请环境不能为空")
    if settings.EXTERNAL_SYSTEM_MODE == "mock":
        return "https://cjdk-jyrc.mock"

    configured = _base_url_mapping()
    try:
        return configured[normalized].rstrip("/")
    except KeyError:
        known = ", ".join(sorted(configured)) or "未配置"
        raise ImproperlyConfigured(
            f"CJDK-JYRC 环境 {environment!r} 未配置基础地址；已配置环境：{known}"
        ) from None


def is_configured_environment(environment: str) -> bool:
    normalized = environment.strip().lower()
    return bool(normalized and normalized in _base_url_mapping())


def channel() -> int:
    return int(_setting("CJDK_JYRC_CHANNEL", "13"))


def scene() -> str:
    return str(_setting("CJDK_JYRC_SCENE", "SC00015"))


def product_id() -> str:
    return str(_setting("CJDK_JYRC_PRODUCT_ID", "CJDK-ZHHX"))


def product_subdivision() -> str:
    return str(_setting("CJDK_JYRC_PRODUCT_SUBDIVISION", "partners"))


def product_subdivision_encode() -> str:
    return str(_setting("CJDK_JYRC_PRODUCT_SUBDIVISION_ENCODE", "202605077231204"))


def business_no() -> str:
    return str(_setting("CJDK_JYRC_BUSINESS_NO", "00000000"))


def default_project_id() -> str:
    return str(_setting("CJDK_JYRC_DEFAULT_PROJECT_ID", ""))


def default_id_type() -> str:
    return str(_setting("CJDK_JYRC_DEFAULT_ID_TYPE", ""))


def form_sign() -> str:
    return str(_setting("CJDK_JYRC_FORM_SIGN", ""))


def timestamp_format() -> str:
    return str(_setting("CJDK_JYRC_TIMESTAMP_FORMAT", "%Y-%m-%d %H:%M:%S"))


def default_template_numbers() -> tuple[str, ...]:
    value = _setting("CJDK_JYRC_FCOS_TEMPLATE_NOS", "2209201448031")
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(item.strip() for item in str(value).split(",") if item.strip())


def _base_url_mapping() -> dict[str, str]:
    configured = getattr(settings, "CJDK_JYRC_BASE_URLS", None)
    if configured is None:
        raw = os.getenv("CJDK_JYRC_BASE_URLS", "{}")
        try:
            configured = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ImproperlyConfigured("CJDK_JYRC_BASE_URLS 必须是 JSON 对象") from exc
    if not isinstance(configured, Mapping):
        raise ImproperlyConfigured("CJDK_JYRC_BASE_URLS 必须是环境到 URL 的映射")

    result: dict[str, str] = {}
    for key, value in configured.items():
        normalized_key = str(key).strip().lower()
        normalized_value = str(value).strip()
        if normalized_key and normalized_value:
            result[normalized_key] = normalized_value
    return result


def _setting(name: str, default: object) -> object:
    if hasattr(settings, name):
        return getattr(settings, name)
    return os.getenv(name, default)
