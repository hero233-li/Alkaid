from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApplicationConfigurationError(ValueError):
    """Raised when application-link business configuration cannot be compiled."""


class IntegrationProfile(BaseModel):
    """Versioned protocol template referenced by product application-link routes."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1, max_length=255)
    version: int = Field(ge=1)
    checksum: str = Field(pattern="^sha256:[0-9a-f]{64}$")
    template: dict[str, Any]
    secret_bindings: dict[str, str] = Field(default_factory=dict, alias="secretBindings")
