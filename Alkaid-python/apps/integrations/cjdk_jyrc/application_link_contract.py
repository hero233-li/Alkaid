from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApplicationLinkCategory(str, Enum):
    SUN_CODE = "SUN_CODE"
    DYNAMIC_LINK = "DYNAMIC_LINK"

    @property
    def display_name(self) -> str:
        return {
            ApplicationLinkCategory.SUN_CODE: "太阳码",
            ApplicationLinkCategory.DYNAMIC_LINK: "动态链接",
        }[self]


class FrozenApplicationLinkRoute(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route_id: str = Field(min_length=1, max_length=255)
    environment: str = Field(min_length=1, max_length=128)
    application_methods: tuple[str, ...] = Field(min_length=1)
    category_code: ApplicationLinkCategory
    integration_profile_id: str = Field(min_length=1, max_length=255)
    integration_profile_version: int = Field(ge=1)
    integration_profile_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    required_fields: tuple[str, ...]
    compiled_request_template: dict[str, Any]
    payload_bindings: dict[str, str]
    secret_bindings: dict[str, str]


class CompiledApplicationLinkPlan(FrozenApplicationLinkRoute):
    def freeze(self) -> FrozenApplicationLinkRoute:
        return FrozenApplicationLinkRoute.model_validate(self.model_dump(mode="python"))
