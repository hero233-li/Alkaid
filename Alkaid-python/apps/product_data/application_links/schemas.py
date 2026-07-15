from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class LinkCategory(str, Enum):
    SUN_CODE = "太阳码"
    DYNAMIC_LINK = "动态链接"


class ApplicationLinkOption(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str


class ApplicationLinkRouteConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    environment: str
    category: LinkCategory
    requiredFields: tuple[str, ...] = ()


class ApplicationLinkProductConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str
    routes: tuple[ApplicationLinkRouteConfig, ...]


class ApplicationLinkPageConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    environments: tuple[ApplicationLinkOption, ...]
    products: tuple[ApplicationLinkProductConfig, ...]
    cooperationProjects: tuple[ApplicationLinkOption, ...] = ()


class ApplicationLinkSubmission(BaseModel):
    """Stable HTTP contract for the application-link page."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    environment: str = Field(
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("env", "environment"),
        serialization_alias="env",
    )
    product: str = Field(min_length=1, max_length=128)
    category: LinkCategory
    cooperationProjectId: str | None = Field(
        default=None,
        max_length=128,
        validation_alias=AliasChoices("cooperationProjectId", "cooperationProject"),
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    # Kept as optional compatibility fields.  The current page does not
    # collect recommender information; a product route can make them required
    # later through its ``requiredFields`` catalog entry without breaking the
    # shared HTTP contract.
    recommender: str | None = Field(default=None, max_length=128)
    recommenderPhone: str | None = Field(default=None, max_length=32)
    loanType: str | None = Field(default=None, min_length=1, max_length=32)
    customerName: str | None = Field(default=None, max_length=128)
    customerPhone: str | None = Field(default=None, max_length=32)
    customerCertificateNo: str | None = Field(default=None, max_length=64)
    customerCompanyName: str | None = Field(default=None, max_length=255)
    customerCompanyCode: str | None = Field(default=None, max_length=128)
    requestJson: dict[str, Any] | None = None
    restoreStatus: str | None = Field(default=None, max_length=64)
    spcode: str | None = Field(default=None, max_length=128)

    @field_validator(
        "environment",
        "product",
        "cooperationProjectId",
        "recommender",
        "recommenderPhone",
        "loanType",
        "customerName",
        "customerPhone",
        "customerCertificateNo",
        "customerCompanyName",
        "customerCompanyCode",
        "restoreStatus",
        "spcode",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class ApplicationLinkExecutionSnapshot(BaseModel):
    """The route selected at Job creation, kept stable for retries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config_version: int = Field(ge=1)
    product: str
    environment: str
    category: LinkCategory
    required_fields: tuple[str, ...]
    # Accepted only so already-created Jobs remain executable after this refactor.
    handler: str | None = None


class ApplicationLinkResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    internalUrl: str
    externalUrl: str
    generatedAt: str


def submission_payload(submission: ApplicationLinkSubmission) -> dict[str, Any]:
    """Canonical Job payload; outer routing fields are never hidden in payload."""
    return {
        "env": submission.environment,
        "product": submission.product,
        "category": submission.category.value,
        **(
            {"cooperationProjectId": submission.cooperationProjectId}
            if submission.cooperationProjectId
            else {}
        ),
        "payload": business_payload(submission),
    }


def business_payload(submission: ApplicationLinkSubmission) -> dict[str, Any]:
    payload = dict(submission.payload)
    legacy_fields = {
        "recommender",
        "recommenderPhone",
        "loanType",
        "customerName",
        "customerPhone",
        "customerCertificateNo",
        "customerCompanyName",
        "customerCompanyCode",
        "restoreStatus",
        "spcode",
    }
    for name in legacy_fields:
        value = getattr(submission, name, None)
        if value is not None:
            payload.setdefault(name, value)
    if submission.requestJson:
        for name, value in submission.requestJson.items():
            payload.setdefault(name, value)
    return payload
