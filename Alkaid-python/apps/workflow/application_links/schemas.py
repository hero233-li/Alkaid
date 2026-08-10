from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from apps.utils.product_Conf.catalog import FrozenApplicationLinkRoute


class LinkCategory(str, Enum):
    SUN_CODE = "太阳码"
    DYNAMIC_LINK = "动态链接"


class ApplicationLinkSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    environment: str = Field(
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("env", "environment"),
        serialization_alias="env",
    )
    product: str = Field(min_length=1, max_length=128)
    category: LinkCategory
    cooperation_project_id: str | None = Field(
        default=None,
        max_length=128,
        validation_alias=AliasChoices("cooperationProjectId", "cooperation_project_id"),
        serialization_alias="cooperationProjectId",
    )
    payload: dict[str, Any] = Field(default_factory=dict)


class ApplicationLinkExecutionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_version: int = Field(ge=1)
    catalog_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    product_code: str
    environment: str
    category: LinkCategory
    normalized_payload: dict[str, Any]
    route: FrozenApplicationLinkRoute
