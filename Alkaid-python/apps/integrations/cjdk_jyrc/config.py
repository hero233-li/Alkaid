import json
import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

CONFIG_DIR = Path(__file__).with_name("configs")
LOCAL_ENVIRONMENT_CONFIG_PATH = CONFIG_DIR / "environments.local.json"


def external_system_mode() -> str:
    local = _local_environment_config()
    if local is not None:
        return str(local["mode"])

    value = str(getattr(settings, "EXTERNAL_SYSTEM_MODE", "mock")).strip().lower()
    if value not in {"mock", "real"}:
        raise ImproperlyConfigured("EXTERNAL_SYSTEM_MODE 必须是 mock 或 real")
    return value


def resolve_base_url(environment: str) -> str:
    normalized = _environment(environment)
    if external_system_mode() == "mock":
        return "https://cjdk-jyrc.mock"

    local = _local_environment_config()
    if local is not None:
        return _local_environment_url(
            local,
            normalized,
            field_name="agreementBaseUrl",
            display_name="协议服务",
        )

    return _resolve_environment_url(
        normalized,
        mapping_name="CJDK_JYRC_BASE_URLS",
        missing_message="CJDK-JYRC",
    )


def resolve_application_link_base_url(environment: str) -> str:
    normalized = _environment(environment)
    if external_system_mode() == "mock":
        return "https://application-link.mock"

    local = _local_environment_config()
    if local is not None:
        return _local_environment_url(
            local,
            normalized,
            field_name="applicationLinkBaseUrl",
            display_name="申请链接服务",
        )

    configured = _url_mapping("APPLICATION_LINK_BASE_URLS")
    if normalized in configured:
        return configured[normalized].rstrip("/")

    legacy = str(getattr(settings, "APPLICATION_LINK_BASE_URL", "")).strip()
    if legacy:
        return legacy.rstrip("/")

    known = ", ".join(sorted(configured)) or "未配置"
    raise ImproperlyConfigured(
        f"申请链接环境 {environment!r} 未配置基础地址；已配置环境：{known}；"
        f"建议创建 {LOCAL_ENVIRONMENT_CONFIG_PATH}"
    )


def application_link_url_mode() -> str:
    local = _local_environment_config()
    if local is not None:
        return str(local["applicationLinkUrlMode"])

    value = str(_setting("APPLICATION_LINK_URL_MODE", "internal")).strip().lower()
    if value not in {"internal", "external"}:
        raise ImproperlyConfigured(
            "APPLICATION_LINK_URL_MODE 必须是 internal 或 external"
        )
    return value


def is_configured_environment(environment: str) -> bool:
    normalized = environment.strip().upper()
    if not normalized:
        return False

    local = _local_environment_config()
    if local is not None:
        environments = local["environments"]
        return isinstance(environments, Mapping) and normalized in environments

    return normalized in _url_mapping("CJDK_JYRC_BASE_URLS")


def clear_environment_config_cache() -> None:
    _load_local_environment_config.cache_clear()


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


def _environment(environment: str) -> str:
    normalized = environment.strip().upper()
    if not normalized:
        raise ImproperlyConfigured("产品申请环境不能为空")
    return normalized


def _local_environment_config() -> dict[str, object] | None:
    return _load_local_environment_config()


@lru_cache(maxsize=1)
def _load_local_environment_config() -> dict[str, object] | None:
    if not LOCAL_ENVIRONMENT_CONFIG_PATH.exists():
        return None

    try:
        raw = json.loads(LOCAL_ENVIRONMENT_CONFIG_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ImproperlyConfigured(
            f"无法读取环境配置文件：{LOCAL_ENVIRONMENT_CONFIG_PATH}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ImproperlyConfigured(
            f"环境配置文件不是有效 JSON：{LOCAL_ENVIRONMENT_CONFIG_PATH}: {exc}"
        ) from exc

    if not isinstance(raw, Mapping):
        raise ImproperlyConfigured("环境配置文件根节点必须是 JSON 对象")

    mode = str(raw.get("mode", "real")).strip().lower()
    if mode not in {"mock", "real"}:
        raise ImproperlyConfigured("环境配置 mode 必须是 mock 或 real")

    url_mode = str(raw.get("applicationLinkUrlMode", "internal")).strip().lower()
    if url_mode not in {"internal", "external"}:
        raise ImproperlyConfigured(
            "环境配置 applicationLinkUrlMode 必须是 internal 或 external"
        )

    configured_environments = raw.get("environments")
    if not isinstance(configured_environments, Mapping) or not configured_environments:
        raise ImproperlyConfigured("环境配置 environments 必须是非空 JSON 对象")

    environments: dict[str, dict[str, str]] = {}
    for key, value in configured_environments.items():
        normalized_key = str(key).strip().upper()
        if not normalized_key:
            raise ImproperlyConfigured("环境代码不能为空")
        if not isinstance(value, Mapping):
            raise ImproperlyConfigured(f"环境 {normalized_key} 的配置必须是 JSON 对象")

        application_link_url = str(value.get("applicationLinkBaseUrl", "")).strip()
        agreement_url = str(value.get("agreementBaseUrl", "")).strip()
        if mode == "real" and not application_link_url:
            raise ImproperlyConfigured(
                f"环境 {normalized_key} 缺少 applicationLinkBaseUrl"
            )
        if mode == "real" and not agreement_url:
            raise ImproperlyConfigured(f"环境 {normalized_key} 缺少 agreementBaseUrl")

        environments[normalized_key] = {
            "applicationLinkBaseUrl": application_link_url,
            "agreementBaseUrl": agreement_url,
        }

    return {
        "mode": mode,
        "applicationLinkUrlMode": url_mode,
        "environments": environments,
    }


def _local_environment_url(
    config: Mapping[str, object],
    environment: str,
    *,
    field_name: str,
    display_name: str,
) -> str:
    environments = config.get("environments")
    if not isinstance(environments, Mapping):
        raise ImproperlyConfigured("环境配置 environments 无效")

    raw_environment = environments.get(environment)
    if not isinstance(raw_environment, Mapping):
        known = ", ".join(sorted(str(item) for item in environments)) or "未配置"
        raise ImproperlyConfigured(
            f"{display_name}环境 {environment!r} 未配置；已配置环境：{known}"
        )

    value = str(raw_environment.get(field_name, "")).strip()
    if not value:
        raise ImproperlyConfigured(
            f"环境 {environment!r} 的 {field_name} 未配置"
        )
    return value.rstrip("/")


def _resolve_environment_url(
    environment: str,
    *,
    mapping_name: str,
    missing_message: str,
) -> str:
    configured = _url_mapping(mapping_name)
    try:
        return configured[environment].rstrip("/")
    except KeyError:
        known = ", ".join(sorted(configured)) or "未配置"
        raise ImproperlyConfigured(
            f"{missing_message} 环境 {environment!r} 未配置基础地址；已配置环境：{known}；"
            f"建议创建 {LOCAL_ENVIRONMENT_CONFIG_PATH}"
        ) from None


def _url_mapping(name: str) -> dict[str, str]:
    configured = getattr(settings, name, None)
    if configured is None:
        raw = os.getenv(name, "{}")
        try:
            configured = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ImproperlyConfigured(f"{name} 必须是 JSON 对象") from exc
    elif isinstance(configured, str):
        try:
            configured = json.loads(configured or "{}")
        except json.JSONDecodeError as exc:
            raise ImproperlyConfigured(f"{name} 必须是 JSON 对象") from exc

    if not isinstance(configured, Mapping):
        raise ImproperlyConfigured(f"{name} 必须是环境到 URL 的映射")

    result: dict[str, str] = {}
    for key, value in configured.items():
        normalized_key = str(key).strip().upper()
        normalized_value = str(value).strip()
        if normalized_key and normalized_value:
            result[normalized_key] = normalized_value
    return result


def _setting(name: str, default: object) -> object:
    if hasattr(settings, name):
        return getattr(settings, name)
    return os.getenv(name, default)
