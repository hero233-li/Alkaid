from __future__ import annotations

import json
import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin

from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.dispatch import receiver
from django.test.signals import setting_changed
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from apps.utils.http.contracts import RetryMode

CONFIG_DIR = Path(__file__).parents[2] / "config" / "application_Conf"
ENVIRONMENT_CONFIG_DIR = CONFIG_DIR / "environments"
ENDPOINT_CONFIG_DIR = CONFIG_DIR / "endpoints"
RUNTIME_CONFIG_DIR = CONFIG_DIR / "runtime"
LOCAL_ENDPOINT_CONFIG_PATH = ENDPOINT_CONFIG_DIR / "endpoints.local.json"
LEGACY_CONFIG_DIR = Path(__file__).parents[2] / "product_applications" / "application" / "configs"
LOCAL_APPLICATION_CONFIG_PATH = RUNTIME_CONFIG_DIR / "application.local.json"
# Compatibility name retained for callers and tests that override the old constant.
LOCAL_ENVIRONMENT_CONFIG_PATH = LOCAL_APPLICATION_CONFIG_PATH
COMPATIBILITY_ENVIRONMENT_CONFIG_PATH = CONFIG_DIR / "environments.local.json"
LEGACY_ENVIRONMENT_CONFIG_PATH = LEGACY_CONFIG_DIR / "environments.local.json"


class EnvironmentSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    agreement_base_url: str
    session_url_template: str | None = Field(default=None, alias="sessionUrlTemplate")
    session_method: Literal["GET", "POST"] = Field(default="GET", alias="sessionMethod")
    verify_ssl: bool = Field(default=True, alias="verifySsl")
    required_cookies: tuple[str, ...] = Field(default_factory=tuple, alias="requiredCookies")
    required_headers: tuple[str, ...] = Field(default_factory=tuple, alias="requiredHeaders")
    required_any_headers: tuple[str, ...] = Field(default_factory=tuple, alias="requiredAnyHeaders")
    forward_session_headers_to_hosts: tuple[str, ...] = Field(
        default_factory=tuple, alias="forwardSessionHeadersToHosts"
    )
    max_redirects: int = Field(default=10, alias="maxRedirects", ge=0, le=20)

    @model_validator(mode="after")
    def normalize_environment_settings(self) -> EnvironmentSettings:
        if not self.forward_session_headers_to_hosts:
            object.__setattr__(
                self,
                "forward_session_headers_to_hosts",
                _default_session_policy(self.agreement_base_url)[
                    "forward_session_headers_to_hosts"
                ],
            )
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


class IdentityEnvironmentSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    video_template: str = Field(alias="videoTemplate")
    photo: PhotoEnvironmentSettings
    sms_lookup: DcppEnvironmentSettings = Field(alias="smsLookup")


class IdentitySettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    endpoints: dict[str, str]
    environments: dict[str, IdentityEnvironmentSettings]
    mock: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_layout(cls, value: object) -> object:
        if not isinstance(value, Mapping) or "environments" in value:
            return value
        video_templates = _mapping(value.get("videoTemplates"), "videoTemplates")
        photo = _mapping(value.get("photo"), "photo")
        sms_lookup = _mapping(value.get("smsLookup"), "smsLookup")
        environment_names = set(video_templates) | set(photo) | set(sms_lookup)
        normalized = dict(value)
        normalized.pop("videoTemplates", None)
        normalized.pop("photo", None)
        normalized.pop("smsLookup", None)
        normalized["environments"] = {
            str(name).upper(): {
                "videoTemplate": video_templates.get(name),
                "photo": photo.get(name),
                "smsLookup": sms_lookup.get(name),
            }
            for name in environment_names
        }
        return normalized

    def endpoint(self, name: str) -> str:
        value = str(self.endpoints.get(name) or "").strip()
        if not value:
            raise RuntimeError(f"身份认证接口未配置：{name}")
        return value

    def video_message_name(self, environment: str) -> str:
        configured = self.environments.get(environment.upper())
        if not configured or not configured.video_template:
            raise RuntimeError(f"未配置 {environment} 的人脸活检原始报文模板")
        return configured.video_template

    def photo_environment(self, environment: str) -> PhotoEnvironmentSettings:
        try:
            return self.environments[environment.upper()].photo
        except KeyError:
            raise RuntimeError(f"未配置 {environment} 的 Photo 环境") from None

    @property
    def video_templates(self) -> dict[str, str]:
        return {name: configured.video_template for name, configured in self.environments.items()}

    @property
    def photo(self) -> dict[str, PhotoEnvironmentSettings]:
        return {name: configured.photo for name, configured in self.environments.items()}

    @property
    def sms_lookup(self) -> dict[str, DcppEnvironmentSettings]:
        return {name: configured.sms_lookup for name, configured in self.environments.items()}


IDENTITY_CONFIG_PATH = RUNTIME_CONFIG_DIR / "identity.local.json"
LEGACY_IDENTITY_CONFIG_PATH = LEGACY_CONFIG_DIR / "identity.local.json"


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImproperlyConfigured(f"无法读取{label}：{path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ImproperlyConfigured(f"{label}根节点必须是 JSON 对象：{path}")
    return raw


def _local_environment_files() -> tuple[Path, ...]:
    return tuple(sorted(ENVIRONMENT_CONFIG_DIR.glob("*.local.json")))


def _endpoint_contract(name: str) -> dict[str, object]:
    if not LOCAL_ENDPOINT_CONFIG_PATH.exists():
        return {}
    configured = _read_json_object(LOCAL_ENDPOINT_CONFIG_PATH, "接口配置")
    return dict(_mapping(configured.get(name), f"endpoints.{name}"))


def _request_path(contract: Mapping[str, object], name: str) -> str:
    configured = _mapping(contract.get(name), name)
    method = str(configured.get("method", "POST")).strip().upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ImproperlyConfigured(f"接口 {name} method 无效：{method}")
    path = str(configured.get("path", "")).strip()
    if not path:
        raise ImproperlyConfigured(f"接口 {name} 缺少 path")
    return path if path.startswith("/") else f"/{path}"


def _absolute_url(base_url: object, path: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        raise ImproperlyConfigured("环境服务缺少 baseUrl")
    return urljoin(f"{base}/", path.lstrip("/"))


def _compose_split_identity_config(runtime: Mapping[str, object]) -> dict[str, object]:
    identity_endpoints = _endpoint_contract("identity")
    photo_endpoints = _endpoint_contract("photo")
    sms_endpoints = _endpoint_contract("smsLookup")
    environment_files = _local_environment_files()
    if not identity_endpoints and not environment_files:
        return dict(runtime)

    endpoint_paths = {
        name: _request_path(identity_endpoints, name)
        for name in (
            "getPublicKey",
            "getPrepareMobile",
            "getAliSdkParams",
            "aliVideoCheck",
            "smsCodeSend",
            "smsCodeCheck",
            "identityCardVerify",
        )
    }
    video_templates = _mapping(runtime.get("videoTemplates"), "videoTemplates")
    photo_defaults = _mapping(runtime.get("photoDefaults"), "photoDefaults")
    sms_defaults = _mapping(runtime.get("smsLookupDefaults"), "smsLookupDefaults")
    photo_delete_path = _request_path(photo_endpoints, "delete")
    sms_query_path = _request_path(sms_endpoints, "query")
    environments: dict[str, object] = {}
    for path in environment_files:
        raw = _read_json_object(path, "环境配置")
        name = _normalize_environment(str(raw.get("environment", "")))
        services = _mapping(raw.get("services"), f"{name}.services")
        photo = _mapping(services.get("photo"), f"{name}.services.photo")
        sms = _mapping(services.get("smsLookup"), f"{name}.services.smsLookup")
        environments[name] = {
            "videoTemplate": video_templates.get(name),
            "photo": {
                **photo_defaults,
                "baseUrl": photo.get("baseUrl"),
                "verifySsl": photo.get("verifySsl", False),
                "deletePath": photo_delete_path,
            },
            "smsLookup": {
                **sms_defaults,
                "url": _absolute_url(sms.get("baseUrl"), sms_query_path),
                "zone": sms.get("zone"),
                "logHostPaths": sms.get("logHostPaths"),
            },
        }
    return {"endpoints": endpoint_paths, "environments": environments}


@lru_cache(maxsize=2)
def get_identity_settings(mode: str | None = None) -> IdentitySettings:
    configured = os.getenv("CJDK_JYRC_IDENTITY_CONFIG", "").strip()
    path = (
        Path(configured)
        if configured
        else _preferred_config_path(IDENTITY_CONFIG_PATH, LEGACY_IDENTITY_CONFIG_PATH)
    )
    split_available = bool(
        _local_environment_files()
        or LOCAL_ENDPOINT_CONFIG_PATH.exists()
    )
    if not path.exists() and not split_available:
        if (mode or "").lower() == "mock":
            return _mock_identity_settings()
        raise RuntimeError(
            "缺少身份认证拆分配置；请按 application_Conf/README.md 将 environments、"
            "endpoints 和 runtime 下的示例复制为 .local.json"
        )
    raw = _read_json_object(path, "身份认证运行配置") if path.exists() else {}
    if "endpoints" not in raw and "environments" not in raw:
        raw = _compose_split_identity_config(raw)
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
            "environments": {
                environment: {
                    "videoTemplate": (
                        "identity_ali_video_check_uc_v1"
                        if environment == "UATC"
                        else "identity_ali_video_check_u12_v1"
                    ),
                    "photo": {"baseUrl": "https://photo.mock"},
                    "smsLookup": {
                        "url": "https://sms-log.mock",
                        "zone": "mock",
                        "logHostPaths": ["/mock"],
                        "maxAttempts": 1,
                        "retryIntervalSeconds": 0,
                    },
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


def request_contract(
    group: str,
    name: str,
    *,
    operation_id: str,
    method: str,
    path: str,
    retry_mode: str = "never",
) -> dict[str, object]:
    """Resolve one request contract, allowing endpoints/<group>.local.json overrides."""

    configured = _mapping(_endpoint_contract(group).get(name), f"{group}.{name}")
    unknown = set(configured) - {"operationId", "method", "path", "retryMode"}
    if unknown:
        raise ImproperlyConfigured(
            f"{group}.{name} 包含未知字段：{', '.join(sorted(unknown))}"
        )
    resolved_method = str(configured.get("method", method)).strip().upper()
    if resolved_method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ImproperlyConfigured(f"{group}.{name} method 无效：{resolved_method}")
    resolved_path = str(configured.get("path", path)).strip()
    if not resolved_path:
        raise ImproperlyConfigured(f"{group}.{name} path 不能为空")
    if not resolved_path.startswith("/"):
        resolved_path = f"/{resolved_path}"
    resolved_retry_mode = str(configured.get("retryMode", retry_mode)).strip().lower()
    try:
        retry = RetryMode(resolved_retry_mode)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"{group}.{name} retryMode 无效：{resolved_retry_mode}"
        ) from exc
    return {
        "operation_id": str(configured.get("operationId", operation_id)).strip(),
        "method": resolved_method,
        "path": resolved_path,
        "retry_mode": retry,
    }


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


def _default_session_policy(base_url: str) -> dict[str, tuple[object, ...]]:
    from urllib.parse import urlsplit

    parsed = urlsplit(base_url)
    host = parsed.hostname or "application-jyrc.mock"
    return {"forward_session_headers_to_hosts": (host,)}


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
            **_default_session_policy(value),
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
        defaults = _default_session_policy(base_url)
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
            forwardSessionHeadersToHosts=policy.get(
                "forwardSessionHeadersToHosts",
                fallback.forward_session_headers_to_hosts
                if fallback
                else defaults["forward_session_headers_to_hosts"],
            ),
            maxRedirects=policy.get("maxRedirects", fallback.max_redirects if fallback else 10),
        )
    return result


def _compose_split_application_config(runtime: Mapping[str, object]) -> dict[str, object]:
    if "environments" in runtime:
        return dict(runtime)
    environment_files = _local_environment_files()
    if not environment_files:
        return dict(runtime)
    endpoint_config = _endpoint_contract("application")
    session = _mapping(endpoint_config.get("session"), "application.session")
    method = str(session.get("method", "GET")).strip().upper()
    if method not in {"GET", "POST"}:
        raise ImproperlyConfigured(f"application.session method 无效：{method}")
    paths = _mapping(session.get("pathByEnvironment"), "application.session.pathByEnvironment")
    environments: dict[str, object] = {}
    for path in environment_files:
        raw = _read_json_object(path, "环境配置")
        name = _normalize_environment(str(raw.get("environment", "")))
        services = _mapping(raw.get("services"), f"{name}.services")
        application = _mapping(services.get("application"), f"{name}.services.application")
        session_path = str(paths.get(name, "")).strip()
        if not session_path:
            raise ImproperlyConfigured(f"application.session 缺少 {name} 的 path")
        environments[name] = {
            "agreementBaseUrl": application.get("baseUrl"),
            "sessionUrlTemplate": _absolute_url(application.get("baseUrl"), session_path),
            "sessionMethod": method,
            "verifySsl": application.get("verifySsl", True),
            "session": {
                "requiredCookies": session.get("requiredCookies", ()),
                "requiredHeaders": session.get("requiredHeaders", ()),
                "requiredAnyHeaders": session.get("requiredAnyHeaders", ()),
            },
            "urlPolicy": application.get("urlPolicy", {}),
        }
    return {**runtime, "environments": environments}


@lru_cache(maxsize=1)
def _load_local_environment_config() -> dict[str, object]:
    path = _preferred_config_path(
        LOCAL_ENVIRONMENT_CONFIG_PATH,
        COMPATIBILITY_ENVIRONMENT_CONFIG_PATH,
        LEGACY_ENVIRONMENT_CONFIG_PATH,
    )
    if not path.exists() and not _local_environment_files():
        return {}
    raw = _read_json_object(path, "CJDK-JYRC 运行配置") if path.exists() else {}
    raw = _compose_split_application_config(raw)
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


def _preferred_config_path(primary: Path, *fallbacks: Path) -> Path:
    for path in (primary, *fallbacks):
        if path.exists():
            return path
    return primary


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
