from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class VerificationPayload(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class VerificationSearchSubmission(VerificationPayload):
    environment: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=128)
    contract_no: str = Field(min_length=1, max_length=128)

    @field_validator("environment", "category", "contract_no")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class VerificationItemUpdateSubmission(VerificationPayload):
    status: str = Field(pattern=r"^(pending|completed)$")


class VerificationAction(str, Enum):
    COMPLETE = "complete"
    SUPPLEMENT = "supplement"
    SUBMIT = "submit"
    APPROVAL_SUBMIT = "approval-submit"
