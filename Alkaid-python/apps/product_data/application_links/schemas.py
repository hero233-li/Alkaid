from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LinkCategory(str, Enum):
    SUN_CODE = "太阳码"
    DYNAMIC_LINK = "动态链接"


class ApplicationLinkSubmission(BaseModel):
    """Stable HTTP contract for the application-link page."""

    model_config = ConfigDict(extra="forbid")

    environment: str = Field(min_length=1, max_length=128)
    product: str = Field(min_length=1, max_length=128)
    category: LinkCategory
    cooperationProject: str = Field(min_length=1, max_length=128)
    # Kept as optional compatibility fields.  The current page does not
    # collect recommender information; a product route can make them required
    # later through its ``requiredFields`` catalog entry without breaking the
    # shared HTTP contract.
    recommender: str | None = Field(default=None, max_length=128)
    recommenderPhone: str | None = Field(default=None, max_length=32)
    loanType: str = Field(min_length=1, max_length=32)
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
        "cooperationProject",
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
    applicationNo: str


def submission_payload(submission: ApplicationLinkSubmission) -> dict[str, Any]:
    return submission.model_dump(mode="json", exclude_none=True)
