from __future__ import annotations

import json
import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Literal

from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.dispatch import receiver
from django.test.signals import setting_changed
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

CONFIG_DIR = Path(__file__).with_name("configs")
LOCAL_ENVIRONMENT_CONFIG_PATH = CONFIG_DIR / "environments.local.json"


class JavaGatewaySettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sdk_dir: Path
    java_executable: Path
    jar: Path
    main_class: str
    output_encoding: str = "gbk"
    timeout_seconds: float = Field(default=120, gt=0)


class EnvironmentSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    agreement_base_url: str
    session: SessionRequirement = Field(default_factory=lambda: SessionRequirement())
    url_policy: UrlPolicy | None = Field(default=None, alias="urlPolicy")

    @model_validator(mode="after")
    def provide_url_policy(self) -> EnvironmentSettings:
        if self.url_policy is None:
            object.__setattr__(self, "url_policy", _default_url_policy(self.agreement_base_url))
        return self


class SessionRequirement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    required_cookies: tuple[str, ...] = Field(default_factory=tuple, alias="requiredCookies")
    required_headers: tuple[str, ...] = Field(default_factory=tuple, alias="requiredHeaders")
    required_any_headers: tuple[str, ...] = Field(
        default_factory=tuple, alias="requiredAnyHeaders"
    )


class UrlPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    allowed_schemes: tuple[Literal["http", "https"], ...] = Field(alias="allowedSchemes")
    allowed_hosts: tuple[str, ...] = Field(alias="allowedHosts", min_length=1)
    allowed_ports: tuple[int, ...] = Field(alias="allowedPorts", min_length=1)
    allow_cross_host_redirect: bool = Field(default=False, alias="allowCrossHostRedirect")
    forward_session_headers_to_hosts: tuple[str, ...] = Field(
        default_factory=tuple, alias="forwardSessionHeadersToHosts"
    )
    max_redirects: int = Field(default=10, alias="maxRedirects", ge=0, le=20)


class ResponseLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    max_json_bytes: int = Field(default=5 * 1024 * 1024, alias="maxJsonBytes", gt=0)
    max_html_bytes: int = Field(default=2 * 1024 * 1024, alias="maxHtmlBytes", gt=0)
    max_redirects: int = Field(default=10, alias="maxRedirects", ge=0, le=20)
    max_agreement_templates: int = Field(default=50, alias="maxAgreementTemplates", gt=0)
    max_preview_documents: int = Field(default=50, alias="maxPreviewDocuments", gt=0)
    max_base64_characters: int = Field(
        default=28 * 1024 * 1024, alias="maxBase64Characters", gt=0
    )
    max_decoded_document_bytes: int = Field(
        default=20 * 1024 * 1024, alias="maxDecodedDocumentBytes", gt=0
    )
    max_total_document_bytes: int = Field(
        default=50 * 1024 * 1024, alias="maxTotalDocumentBytes", gt=0
    )


class CjdkJyrcSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["mock", "real"]
    application_link_url_mode: Literal["internal", "external"]
    java_gateway: JavaGatewaySettings
    environments: dict[str, EnvironmentSettings]
    response_limits: ResponseLimits = Field(
        default_factory=ResponseLimits, alias="responseLimits"
    )

    @model_validator(mode="after")
    def validate_real_environment_urls(self) -> CjdkJyrcSettings:
        if self.mode == "real":
            missing = [
                name
                for name, environment in self.environments.items()
                if not environment.agreement_base_url.strip()
            ]
            if missing:
                raise ValueError("真实模式缺少 agreementBaseUrl：" + ", ".join(sorted(missing)))
        return self

    def environment(self, environment: str) -> EnvironmentSettings:
        normalized = _normalize_environment(environment)
        try:
            return self.environments[normalized]
        except KeyError:
            known = ", ".join(sorted(self.environments)) or "未配置"
            raise ImproperlyConfigured(
                f"CJDK-JYRC 环境 {normalized!r} 未配置；已配置环境：{known}"
            ) from None


@lru_cache(maxsize=1)
def get_cjdk_jyrc_settings() -> CjdkJyrcSettings:
    local = _load_local_environment_config()
    try:
        mode = str(local.get("mode", _setting("EXTERNAL_SYSTEM_MODE", "mock"))).strip().lower()
        url_mode = (
            str(
                local.get(
                    "applicationLinkUrlMode",
                    _setting("APPLICATION_LINK_URL_MODE", "internal"),
                )
            )
            .strip()
            .lower()
        )
        gateway = _gateway_settings(local.get("javaGateway"))
        environments = _environment_settings(local.get("environments"), mode=mode)
        return CjdkJyrcSettings(
            mode=mode,
            application_link_url_mode=url_mode,
            java_gateway=gateway,
            environments=environments,
            responseLimits=local.get("responseLimits", {}),
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise ImproperlyConfigured(f"CJDK-JYRC 配置无效：{exc}") from exc


def external_system_mode() -> str:
    return get_cjdk_jyrc_settings().mode


def application_link_url_mode() -> str:
    return get_cjdk_jyrc_settings().application_link_url_mode


def resolve_base_url(environment: str) -> str:
    if external_system_mode() == "mock":
        return "https://cjdk-jyrc.mock"
    return get_cjdk_jyrc_settings().environment(environment).agreement_base_url.rstrip("/")


def is_configured_environment(environment: str) -> bool:
    normalized = environment.strip().upper()
    return bool(normalized and normalized in get_cjdk_jyrc_settings().environments)


def java_sdk_dir() -> Path:
    return get_cjdk_jyrc_settings().java_gateway.sdk_dir


def java_executable() -> Path:
    return get_cjdk_jyrc_settings().java_gateway.java_executable


def java_jar() -> Path:
    return get_cjdk_jyrc_settings().java_gateway.jar


def java_main_class() -> str:
    return get_cjdk_jyrc_settings().java_gateway.main_class


def java_output_encoding() -> str:
    return get_cjdk_jyrc_settings().java_gateway.output_encoding


def java_timeout_seconds() -> float:
    return get_cjdk_jyrc_settings().java_gateway.timeout_seconds


def resolve_secret(reference: str) -> str:
    local_secrets = _load_local_environment_config().get("secrets", {})
    if isinstance(local_secrets, Mapping):
        local_value = str(local_secrets.get(reference, "")).strip()
        if local_value:
            return local_value

    setting_names = {
        "cjdkJyrc.applicationLink.appId": "CJDK_JYRC_APPLICATION_LINK_APP_ID",
        "cjdkJyrc.applicationLink.privateKey": "CJDK_JYRC_APPLICATION_LINK_PRIVATE_KEY",
        "cjdkJyrc.applicationLink.publicKey": "CJDK_JYRC_APPLICATION_LINK_PUBLIC_KEY",
    }
    try:
        setting_name = setting_names[reference]
    except KeyError:
        raise KeyError(reference) from None
    value = str(_setting(setting_name, "")).strip()
    if value:
        return value
    if external_system_mode() == "mock":
        return f"mock-{setting_name.lower().replace('_', '-')}"
    raise ImproperlyConfigured(f"{setting_name} 未配置")


def validate_cjdk_jyrc_readiness(environments: set[str] | None = None) -> None:
    configured = get_cjdk_jyrc_settings()
    if configured.mode != "real":
        return
    gateway = configured.java_gateway
    sdk_root = gateway.sdk_dir
    java_path = _resolve_runtime_path(gateway.java_executable, sdk_root)
    jar_path = _resolve_runtime_path(gateway.jar, sdk_root)
    if not sdk_root.is_dir():
        raise ImproperlyConfigured(f"Java SDK 目录不存在：{sdk_root}")
    if not java_path.is_file():
        raise ImproperlyConfigured(f"Java 可执行文件不存在：{java_path}")
    if not jar_path.is_file():
        raise ImproperlyConfigured(f"申请链接 Jar 不存在：{jar_path}")
    if not gateway.main_class.strip():
        raise ImproperlyConfigured("javaGateway.mainClass 未配置")
    if gateway.timeout_seconds <= 0:
        raise ImproperlyConfigured("javaGateway.timeoutSeconds 必须大于 0")
    for environment in environments or set(configured.environments):
        value = configured.environment(environment).agreement_base_url.strip()
        if not value:
            raise ImproperlyConfigured(f"环境 {environment} 缺少 agreementBaseUrl")


def clear_environment_config_cache() -> None:
    _load_local_environment_config.cache_clear()
    get_cjdk_jyrc_settings.cache_clear()


@receiver(setting_changed)
def _clear_settings_cache_after_override(*, setting: str, **_: object) -> None:
    if setting.startswith(("CJDK_JYRC_", "APPLICATION_LINK_", "EXTERNAL_SYSTEM_MODE")):
        clear_environment_config_cache()


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


def _gateway_settings(raw: object) -> JavaGatewaySettings:
    local = _mapping(raw, "javaGateway")
    allowed = {
        "sdkDir",
        "javaExecutable",
        "jar",
        "mainClass",
        "outputEncoding",
        "timeoutSeconds",
    }
    unknown = set(local) - allowed
    if unknown:
        raise ValueError("javaGateway 包含未知字段：" + ", ".join(sorted(unknown)))
    return JavaGatewaySettings(
        sdk_dir=Path(_local_or_setting(local, "sdkDir", "APPLICATION_LINK_JAVA_SDK_DIR", ".")),
        java_executable=Path(
            _local_or_setting(local, "javaExecutable", "APPLICATION_LINK_JAVA_EXECUTABLE", "java")
        ),
        jar=Path(
            _local_or_setting(local, "jar", "APPLICATION_LINK_JAVA_JAR", "application-link.jar")
        ),
        main_class=_local_or_setting(
            local,
            "mainClass",
            "APPLICATION_LINK_JAVA_MAIN_CLASS",
            "mock.ApplicationLinkMain",
        ),
        output_encoding=_local_or_setting(
            local,
            "outputEncoding",
            "APPLICATION_LINK_JAVA_OUTPUT_ENCODING",
            "gbk",
        ),
        timeout_seconds=float(
            _local_or_setting(
                local,
                "timeoutSeconds",
                "APPLICATION_LINK_JAVA_TIMEOUT_SECONDS",
                "120",
            )
        ),
    )


def _default_url_policy(base_url: str) -> UrlPolicy:
    from urllib.parse import urlsplit

    parsed = urlsplit(base_url)
    scheme = parsed.scheme or "https"
    host = parsed.hostname or "cjdk-jyrc.mock"
    port = parsed.port or (443 if scheme == "https" else 80)
    return UrlPolicy(
        allowedSchemes=[scheme],
        allowedHosts=[host],
        allowedPorts=[port],
        forwardSessionHeadersToHosts=[host],
    )


def _environment_settings(raw: object, *, mode: str) -> dict[str, EnvironmentSettings]:
    local = _mapping(raw, "environments")
    configured = _url_mapping("CJDK_JYRC_BASE_URLS")
    if mode == "mock" and not configured and not local:
        configured = {name: "https://cjdk-jyrc.mock" for name in ("UAT1", "UAT2", "UATC")}
    result = {
        key: EnvironmentSettings(
            agreement_base_url=value.rstrip("/"),
            session=(
                SessionRequirement(
                    requiredCookies=("JSESSIONID", "token_id"),
                    requiredAnyHeaders=("X-Token", "X-FCOS-SESSIONID"),
                )
                if mode == "mock"
                else SessionRequirement()
            ),
            urlPolicy=_default_url_policy(value),
        )
        for key, value in configured.items()
    }
    for raw_name, raw_environment in local.items():
        name = _normalize_environment(str(raw_name))
        values = _mapping(raw_environment, f"environments.{name}")
        unknown = set(values) - {"agreementBaseUrl", "session", "urlPolicy"}
        if unknown:
            raise ValueError(f"environments.{name} 包含未知字段：{', '.join(sorted(unknown))}")
        fallback_url = str(values.get("agreementBaseUrl", "")).strip().rstrip("/")
        fallback = result.get(name)
        if fallback is None and not fallback_url:
            raise ValueError(f"environments.{name}.agreementBaseUrl 不能为空")
        base_url = fallback_url or (fallback.agreement_base_url if fallback else "")
        result[name] = EnvironmentSettings(
            agreement_base_url=base_url,
            session=values.get("session", fallback.session if fallback else {}),
            urlPolicy=values.get(
                "urlPolicy", fallback.url_policy if fallback else _default_url_policy(base_url)
            ),
        )
    return result


@lru_cache(maxsize=1)
def _load_local_environment_config() -> dict[str, object]:
    if not LOCAL_ENVIRONMENT_CONFIG_PATH.exists():
        return {}
    try:
        raw = json.loads(LOCAL_ENVIRONMENT_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImproperlyConfigured(
            f"无法读取 CJDK-JYRC 环境配置：{LOCAL_ENVIRONMENT_CONFIG_PATH}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise ImproperlyConfigured("CJDK-JYRC 环境配置根节点必须是 JSON 对象")
    allowed = {
        "mode", "applicationLinkUrlMode", "javaGateway", "environments", "secrets",
        "responseLimits",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ImproperlyConfigured("CJDK-JYRC 环境配置包含未知字段：" + ", ".join(sorted(unknown)))
    return raw


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} 必须是 JSON 对象")
    return value


def _local_or_setting(
    local: Mapping[str, object],
    local_name: str,
    setting_name: str,
    default: str,
) -> str:
    if local_name in local:
        return str(local[local_name]).strip()
    return str(_setting(setting_name, default)).strip()


def _url_mapping(name: str) -> dict[str, str]:
    configured = _setting(name, {})
    if isinstance(configured, str):
        try:
            configured = json.loads(configured or "{}")
        except json.JSONDecodeError as exc:
            raise ImproperlyConfigured(f"{name} 必须是 JSON 对象") from exc
    if not isinstance(configured, Mapping):
        raise ImproperlyConfigured(f"{name} 必须是环境到 URL 的映射")
    return {
        str(key).strip().upper(): str(value).strip()
        for key, value in configured.items()
        if str(key).strip() and str(value).strip()
    }


def _normalize_environment(environment: str) -> str:
    normalized = environment.strip().upper()
    if not normalized:
        raise ImproperlyConfigured("产品申请环境不能为空")
    return normalized


def _resolve_runtime_path(value: Path, sdk_root: Path) -> Path:
    return value if value.is_absolute() else sdk_root / value


def _setting(name: str, default: object) -> object:
    if hasattr(django_settings, name):
        return getattr(django_settings, name)
    return os.getenv(name, default)
