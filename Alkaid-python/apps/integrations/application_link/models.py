from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GenerateApplicationLinkRequest(BaseModel):
    """Canonical request used by the one-call external link contract."""

    model_config = ConfigDict(frozen=True)

    env: str = Field(min_length=1, max_length=128)
    product: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=32)
    cooperation_project_id: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any]

    @model_validator(mode="after")
    def reject_conflicting_payload_authority(self) -> "GenerateApplicationLinkRequest":
        authoritative = {
            "env": self.env,
            "product": self.product,
            "category": self.category,
            "cooperationProjectId": self.cooperation_project_id,
        }
        conflicts = [
            name
            for name, expected in authoritative.items()
            if name in self.payload and self.payload[name] != expected
        ]
        if conflicts:
            raise ValueError("payload 与外层权威字段冲突：" + ", ".join(sorted(conflicts)))
        return self

    def external_request(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "env": self.env,
            "product": self.product,
            "category": self.category,
            "payload": self.payload,
        }
        if self.cooperation_project_id:
            value["cooperationProjectId"] = self.cooperation_project_id
        return value


class ApplicationLinks(BaseModel):
    model_config = ConfigDict(frozen=True)

    internal_url: str = Field(min_length=1)
    external_url: str = Field(min_length=1)


class GenerateApplicationLinkEnvelope(BaseModel):
    code: str
    data: ApplicationLinks
