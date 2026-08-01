from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkbenchFormField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(max_length=128)
    enabled: bool = True
    type: Literal["text", "file"] = "text"
    name: str = Field(min_length=1, max_length=255)
    value: str = Field(default="", max_length=1_000_000)
    filePartName: str | None = Field(default=None, max_length=255)
    fileName: str | None = Field(default=None, max_length=255)
    contentType: str | None = Field(default=None, max_length=255)


class WorkbenchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]
    url: str = Field(min_length=1, max_length=8192)
    headers: dict[str, str] = Field(default_factory=dict)
    bodyMode: Literal["none", "json", "form-urlencoded", "form-data", "raw"] = "none"
    body: str = Field(default="", max_length=2_000_000)
    formFields: list[WorkbenchFormField] = Field(default_factory=list, max_length=200)
    timeoutSeconds: int = Field(default=30, ge=1, le=120)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("URL 必须是完整的 HTTP 或 HTTPS 地址")
        return value

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 100:
            raise ValueError("请求头不能超过 100 个")
        return {
            str(name).strip(): str(header_value)
            for name, header_value in value.items()
            if str(name).strip()
        }


class RenameHistorySubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()
