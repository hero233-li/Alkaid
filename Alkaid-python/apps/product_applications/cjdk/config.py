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


class EnvironmentSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    agreement_base_url: str
    session_url_template: str | None = Field(default=None, alias="sessionUrlTemplate")
    session_method: Literal["GET", "POST"] = Field(default="GET", alias="sessionMethod")
    verify_ssl: bool = Field(default=True, alias="verifySsl")
    required_cookies: tuple[str, ...] = Field(default_factory=tuple, alias="requiredCookies")
    required_headers: tuple[str, ...] = Field(default_factory=tuple, alias="requiredHeaders")
    required_any_headers: tuple[str, ...] = Field(default_factory=tuple, alias="requiredAnyHeaders")
    allowed_schemes: tuple[Literal["http", "https"], ...] = Field(
        default_factory=tuple, alias="allowedSchemes"
    )
    allowed_hosts: tuple[str, ...] = Field(default_factory=tuple, alias="allowedHosts")
    allowed_ports: tuple[int, ...] = Field(default_factory=tuple, alias="allowedPorts")
    allow_cross_host_redirect: bool = Field(default=False, alias="allowCrossHostRedirect")
    forward_session_headers_to_hosts: tuple[str, ...] = Field(
        default_factory=tuple, alias="forwardSessionHeadersToHosts"
    )
    max_redirects: int = Field(default=10, alias="maxRedirects", ge=0, le=20)

    @model_validator(mode="after")
    def normalize_environment_settings(self) -> EnvironmentSettings:
        if not self.allowed_hosts:
            defaults = _default_url_policy(self.agreement_base_url)
            for name in (
                "allowed_schemes",
                "allowed_hosts",
                "allowed_ports",
                "forward_session_headers_to_hosts",
            ):
                object.__setattr__(self, name, defaults[name])
        if self.session_url_template is not None:
            template = self.session_url_template.strip()
            if not template:
                raise ValueError("sessionUrlTemplate 不能为空")
            if "{auth}" not in template:
                raise ValueError("sessionUrlTemplate 必须包含 {auth} 占位符")
            object.__setattr__(self, "session_url_template", template)
        return self

    @property
    def session(self) -> EnvironmentSettings:
        return self

    @property
    def url_policy(self) -> EnvironmentSettings:
        return self


class CjdkJyrcSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    mode: Literal["mock", "real"]
    application_link_url_mode: Literal["internal", "external"]
    environments: dict[str, EnvironmentSettings]
    sdk_dir: Path = Path(".")
    java_executable: Path = Path("java")
    jar: Path = Path("application-link.jar")
    main_class: str = "mock.ApplicationLinkMain"
    output_encoding: str = "gbk"
    timeout_seconds: float = Field(default=120, gt=0)
    max_json_bytes: int = Field(default=5 * 1024 * 1024, alias="maxJsonBytes", gt=0)
    max_html_bytes: int = Field(default=2 * 1024 * 1024, alias="maxHtmlBytes", gt=0)
    max_redirects: int = Field(default=10, alias="maxRedirects", ge=0, le=20)
    max_agreement_templates: int = Field(default=50, alias="maxAgreementTemplates", gt=0)
    max_preview_documents: int = Field(default=50, alias="maxPreviewDocuments", gt=0)
    max_base64_characters: int = Field(default=28 * 1024 * 1024, alias="maxBase64Characters", gt=0)
    max_decoded_document_bytes: int = Field(
        default=20 * 1024 * 1024, alias="maxDecodedDocumentBytes", gt=0
    )
    max_total_document_bytes: int = Field(
        default=50 * 1024 * 1024, alias="maxTotalDocumentBytes", gt=0
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

    @property
    def java_gateway(self) -> CjdkJyrcSettings:
        return self

    @property
    def response_limits(self) -> CjdkJyrcSettings:
        return self


class PhotoEnvironmentSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    base_url: str = Field(alias="baseUrl")
    delete_path: str = Field(default="/DelectCertiAction.json", alias="deletePath")
    timeout_seconds: int = Field(default=60, alias="timeoutSeconds", ge=1)
    verify_ssl: bool = Field(default=False, alias="verifySsl")
    headers: dict[str, str] = Field(default_factory=dict)


class DcppEnvironmentSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    url: str
    zone: str
    log_host_paths: tuple[str, ...] = Field(alias="logHostPaths")
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=10, alias="timeoutSeconds", ge=1)
    max_attempts: int = Field(default=10, alias="maxAttempts", ge=1)
    retry_interval_seconds: float = Field(default=1.0, alias="retryIntervalSeconds", ge=0)


class IdentitySettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    endpoints: dict[str, str]
    video_templates: dict[str, str] = Field(alias="videoTemplates")
    photo: dict[str, PhotoEnvironmentSettings]
    sms_lookup: dict[str, DcppEnvironmentSettings] = Field(alias="smsLookup")
    mock: bool = False

    def endpoint(self, name: str) -> str:
        value = str(self.endpoints.get(name) or "").strip()
        if not value:
            raise RuntimeError(f"身份认证接口未配置：{name}")
        return value

    def video_message_name(self, environment: str) -> str:
        name = self.video_templates.get(environment.upper())
        if not name:
            raise RuntimeError(f"未配置 {environment} 的人脸活检原始报文模板")
        return name

    def photo_environment(self, environment: str) -> PhotoEnvironmentSettings:
        try:
            return self.photo[environment.upper()]
        except KeyError:
            raise RuntimeError(f"未配置 {environment} 的 Photo 环境") from None


IDENTITY_CONFIG_PATH = CONFIG_DIR / "identity.local.json"


@lru_cache(maxsize=2)
def get_identity_settings(mode: str | None = None) -> IdentitySettings:
    configured = os.getenv("CJDK_JYRC_IDENTITY_CONFIG", "").strip()
    path = Path(configured) if configured else IDENTITY_CONFIG_PATH
    if not path.exists():
        if (mode or "").lower() == "mock":
            return _mock_identity_settings()
        raise RuntimeError(
            f"缺少身份认证配置文件：{path}；"
            "请复制 identity.local.example.json 为 identity.local.json"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("identity.local.json 必须是 JSON 对象")
    return IdentitySettings.model_validate(raw)


def _mock_identity_settings() -> IdentitySettings:
    environments = ("UAT1", "UAT2", "UATC")
    return IdentitySettings.model_validate(
        {
            "mock": True,
            "endpoints": {
                "getPublicKey": "/mock/identity/public-key",
                "getPrepareMobile": "/mock/identity/prepare-mobile",
                "getAliSdkParams": "/mock/identity/ali-sdk-params",
                "aliVideoCheck": "/mock/identity/video-check",
                "smsCodeSend": "/mock/identity/sms-send",
                "smsCodeCheck": "/mock/identity/sms-check",
                "identityCardVerify": "/mock/identity/card-verify",
            },
            "videoTemplates": {
                environment: (
                    "identity_ali_video_check_uc_v1"
                    if environment == "UATC"
                    else "identity_ali_video_check_u12_v1"
                )
                for environment in environments
            },
            "photo": {
                environment: {"baseUrl": "https://photo.mock"} for environment in environments
            },
            "smsLookup": {
                environment: {
                    "url": "https://sms-log.mock",
                    "zone": "mock",
                    "logHostPaths": ["/mock"],
                    "maxAttempts": 1,
                    "retryIntervalSeconds": 0,
                }
                for environment in environments
            },
        }
    )


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
        limits = _response_limits(local.get("responseLimits"))
        return CjdkJyrcSettings(
            mode=mode,
            application_link_url_mode=url_mode,
            environments=environments,
            **gateway,
            **limits,
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise ImproperlyConfigured(f"CJDK-JYRC 配置无效：{exc}") from exc


def external_system_mode() -> str:
    return get_cjdk_jyrc_settings().mode


def resolve_base_url(environment: str) -> str:
    if external_system_mode() == "mock":
        return "https://cjdk-jyrc.mock"
    return get_cjdk_jyrc_settings().environment(environment).agreement_base_url.rstrip("/")


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
    missing: list[str] = []
    gateway = configured.java_gateway
    sdk_root = gateway.sdk_dir
    java_path = _resolve_runtime_path(gateway.java_executable, sdk_root)
    jar_path = _resolve_runtime_path(gateway.jar, sdk_root)
    if not sdk_root.is_dir():
        missing.append(f"Java SDK 目录：{sdk_root}")
    if not java_path.is_file():
        missing.append(f"Java 可执行文件：{java_path}")
    if not jar_path.is_file():
        missing.append(f"申请链接 Jar：{jar_path}")
    if not gateway.main_class.strip():
        missing.append("javaGateway.mainClass")
    if gateway.timeout_seconds <= 0:
        missing.append("有效的 javaGateway.timeoutSeconds")
    for environment in environments or set(configured.environments):
        value = configured.environment(environment).agreement_base_url.strip()
        if not value:
            missing.append(f"环境 {environment} agreementBaseUrl")

    # The supplied patch does not contain the real startApply contract. Keep real
    # mode unavailable until both values are explicitly supplied; never guess it.
    missing.extend(("startApply 接口路径", "startApply 原始报文模板"))
    try:
        identity = get_identity_settings("real")
        for environment in environments or set(configured.environments):
            normalized = environment.upper()
            if normalized not in identity.video_templates:
                missing.append(f"环境 {normalized} 人脸报文模板")
            if normalized not in identity.photo:
                missing.append(f"环境 {normalized} Photo 配置")
            if normalized not in identity.sms_lookup:
                missing.append(f"环境 {normalized} DCPP 短信查询配置")
    except (OSError, RuntimeError, ValueError) as exc:
        missing.append(str(exc))
    if missing:
        raise ImproperlyConfigured("CJDK 真实模式缺少：" + "；".join(missing))


def clear_environment_config_cache() -> None:
    _load_local_environment_config.cache_clear()
    get_cjdk_jyrc_settings.cache_clear()
    get_identity_settings.cache_clear()


@receiver(setting_changed)
def _clear_settings_cache_after_override(*, setting: str, **_: object) -> None:
    if setting.startswith(("CJDK_JYRC_", "APPLICATION_LINK_", "EXTERNAL_SYSTEM_MODE")):
        clear_environment_config_cache()


def channel() -> int:
    return int(_setting("CJDK_JYRC_CHANNEL", "13"))


def scene() -> str:
    return str(_setting("CJDK_JYRC_SCENE", "SC00015"))


def product_subdivision() -> str:
    return str(_setting("CJDK_JYRC_PRODUCT_SUBDIVISION", "partners"))


def business_no() -> str:
    return str(_setting("CJDK_JYRC_BUSINESS_NO", "00000000"))


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


def _gateway_settings(raw: object) -> dict[str, object]:
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
    return {
        "sdk_dir": Path(_local_or_setting(local, "sdkDir", "APPLICATION_LINK_JAVA_SDK_DIR", ".")),
        "java_executable": Path(
            _local_or_setting(local, "javaExecutable", "APPLICATION_LINK_JAVA_EXECUTABLE", "java")
        ),
        "jar": Path(
            _local_or_setting(local, "jar", "APPLICATION_LINK_JAVA_JAR", "application-link.jar")
        ),
        "main_class": _local_or_setting(
            local, "mainClass", "APPLICATION_LINK_JAVA_MAIN_CLASS", "mock.ApplicationLinkMain"
        ),
        "output_encoding": _local_or_setting(
            local, "outputEncoding", "APPLICATION_LINK_JAVA_OUTPUT_ENCODING", "gbk"
        ),
        "timeout_seconds": float(
            _local_or_setting(
                local, "timeoutSeconds", "APPLICATION_LINK_JAVA_TIMEOUT_SECONDS", "120"
            )
        ),
    }


def _response_limits(raw: object) -> dict[str, object]:
    values = _mapping(raw, "responseLimits")
    names = {
        "maxJsonBytes": "max_json_bytes",
        "maxHtmlBytes": "max_html_bytes",
        "maxRedirects": "max_redirects",
        "maxAgreementTemplates": "max_agreement_templates",
        "maxPreviewDocuments": "max_preview_documents",
        "maxBase64Characters": "max_base64_characters",
        "maxDecodedDocumentBytes": "max_decoded_document_bytes",
        "maxTotalDocumentBytes": "max_total_document_bytes",
    }
    unknown = set(values) - names.keys()
    if unknown:
        raise ValueError("responseLimits 包含未知字段：" + ", ".join(sorted(unknown)))
    return {names[key]: value for key, value in values.items()}


def _default_url_policy(base_url: str) -> dict[str, tuple[object, ...]]:
    from urllib.parse import urlsplit

    parsed = urlsplit(base_url)
    scheme = parsed.scheme or "https"
    host = parsed.hostname or "cjdk-jyrc.mock"
    port = parsed.port or (443 if scheme == "https" else 80)
    return {
        "allowed_schemes": (scheme,),
        "allowed_hosts": (host,),
        "allowed_ports": (port,),
        "forward_session_headers_to_hosts": (host,),
    }


def _environment_settings(raw: object, *, mode: str) -> dict[str, EnvironmentSettings]:
    local = _mapping(raw, "environments")
    configured = _url_mapping("CJDK_JYRC_BASE_URLS")
    if mode == "mock" and not configured and not local:
        configured = {name: "https://cjdk-jyrc.mock" for name in ("UAT1", "UAT2", "UATC")}
    result = {
        key: EnvironmentSettings(
            agreement_base_url=value.rstrip("/"),
            requiredCookies=("JSESSIONID", "token_id") if mode == "mock" else (),
            requiredAnyHeaders=("X-Token", "X-FCOS-SESSIONID") if mode == "mock" else (),
            **_default_url_policy(value),
        )
        for key, value in configured.items()
    }
    for raw_name, raw_environment in local.items():
        name = _normalize_environment(str(raw_name))
        values = _mapping(raw_environment, f"environments.{name}")
        unknown = set(values) - {
            "agreementBaseUrl",
            "sessionUrlTemplate",
            "sessionMethod",
            "verifySsl",
            "session",
            "urlPolicy",
        }
        if unknown:
            raise ValueError(f"environments.{name} 包含未知字段：{', '.join(sorted(unknown))}")
        fallback_url = str(values.get("agreementBaseUrl", "")).strip().rstrip("/")
        fallback = result.get(name)
        if fallback is None and not fallback_url:
            raise ValueError(f"environments.{name}.agreementBaseUrl 不能为空")
        base_url = fallback_url or (fallback.agreement_base_url if fallback else "")
        session = _mapping(values.get("session"), f"environments.{name}.session")
        policy = _mapping(values.get("urlPolicy"), f"environments.{name}.urlPolicy")
        defaults = _default_url_policy(base_url)
        result[name] = EnvironmentSettings(
            agreement_base_url=base_url,
            sessionUrlTemplate=values.get(
                "sessionUrlTemplate",
                fallback.session_url_template if fallback else None,
            ),
            sessionMethod=values.get(
                "sessionMethod",
                fallback.session_method if fallback else "GET",
            ),
            verifySsl=values.get(
                "verifySsl",
                fallback.verify_ssl if fallback else True,
            ),
            requiredCookies=session.get(
                "requiredCookies", fallback.required_cookies if fallback else ()
            ),
            requiredHeaders=session.get(
                "requiredHeaders", fallback.required_headers if fallback else ()
            ),
            requiredAnyHeaders=session.get(
                "requiredAnyHeaders", fallback.required_any_headers if fallback else ()
            ),
            allowedSchemes=policy.get(
                "allowedSchemes",
                fallback.allowed_schemes if fallback else defaults["allowed_schemes"],
            ),
            allowedHosts=policy.get(
                "allowedHosts", fallback.allowed_hosts if fallback else defaults["allowed_hosts"]
            ),
            allowedPorts=policy.get(
                "allowedPorts", fallback.allowed_ports if fallback else defaults["allowed_ports"]
            ),
            allowCrossHostRedirect=policy.get(
                "allowCrossHostRedirect", fallback.allow_cross_host_redirect if fallback else False
            ),
            forwardSessionHeadersToHosts=policy.get(
                "forwardSessionHeadersToHosts",
                fallback.forward_session_headers_to_hosts
                if fallback
                else defaults["forward_session_headers_to_hosts"],
            ),
            maxRedirects=policy.get("maxRedirects", fallback.max_redirects if fallback else 10),
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
        "mode",
        "applicationLinkUrlMode",
        "javaGateway",
        "environments",
        "secrets",
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
