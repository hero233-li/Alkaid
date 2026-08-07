from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


CONFIG_ROOT = Path(__file__).resolve().parents[1] / "configs"
DEFAULT_CONFIG_PATH = CONFIG_ROOT / "identity.local.json"


class IdentityEndpointPaths(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    get_public_key: str = Field(alias="getPublicKey")
    get_prepare_mobile: str = Field(alias="getPrepareMobile")
    get_ali_sdk_params: str = Field(alias="getAliSdkParams")
    ali_video_check: str = Field(alias="aliVideoCheck")
    sms_code_send: str = Field(alias="smsCodeSend")
    sms_code_check: str = Field(alias="smsCodeCheck")
    identity_card_verify: str = Field(alias="identityCardVerify")


class PhotoEnvironmentSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    base_url: str = Field(alias="baseUrl")
    delete_path: str = Field(default="/DelectCertiAction.json", alias="deletePath")
    timeout_seconds: int = Field(default=60, alias="timeoutSeconds", ge=1)
    verify_ssl: bool = Field(default=False, alias="verifySsl")
    headers: dict[str, str] = Field(default_factory=dict)


class SmsLookupEnvironmentSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    url: str
    zone: str
    log_host_paths: tuple[str, ...] = Field(alias="logHostPaths")
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=10, alias="timeoutSeconds", ge=1)
    max_attempts: int = Field(default=10, alias="maxAttempts", ge=1)
    retry_interval_seconds: float = Field(
        default=1.0, alias="retryIntervalSeconds", ge=0
    )


class IdentitySettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    endpoints: IdentityEndpointPaths
    video_templates: dict[str, str] = Field(alias="videoTemplates")
    photo: dict[str, PhotoEnvironmentSettings]
    sms_lookup: dict[str, SmsLookupEnvironmentSettings] = Field(alias="smsLookup")

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

    def sms_lookup_environment(self, environment: str) -> SmsLookupEnvironmentSettings:
        try:
            return self.sms_lookup[environment.upper()]
        except KeyError:
            raise RuntimeError(f"未配置 {environment} 的短信日志查询环境") from None


@lru_cache(maxsize=1)
def get_identity_settings() -> IdentitySettings:
    configured = os.getenv("CJDK_JYRC_IDENTITY_CONFIG", "").strip()
    path = Path(configured) if configured else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise RuntimeError(
            f"缺少身份认证配置文件：{path}；请复制 identity.local.example.json 为 identity.local.json"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("identity.local.json 必须是 JSON 对象")
    return IdentitySettings.model_validate(raw)
