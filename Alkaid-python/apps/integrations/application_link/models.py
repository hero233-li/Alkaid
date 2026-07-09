from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateApplicationRequest(BaseModel):
    """Semantic input accepted by the external application-link adapter."""

    model_config = ConfigDict(frozen=True)

    product: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=32)
    payload: dict[str, Any]


class GenerateLinksRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    application_no: str = Field(min_length=1, max_length=128)
    product: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=32)


class ApplicationReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    application_no: str


class ApplicationLinks(BaseModel):
    model_config = ConfigDict(frozen=True)

    internal_url: str
    external_url: str


class CreateApplicationEnvelope(BaseModel):
    code: str
    data: ApplicationReference


class GenerateLinksEnvelope(BaseModel):
    code: str
    data: ApplicationLinks
