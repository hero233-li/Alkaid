from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from apps.integrations.verification_approval.models import VerificationTask


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


class VerificationOperation(str, Enum):
    SEARCH = "search"
    CLAIM = "claim"
    RETURN = "return"
    REFRESH = "refresh"
    ITEM_UPDATE = "item-update"
    ACTION = "action"


class VerificationCommand(VerificationPayload):
    operation: VerificationOperation
    data: dict[str, object]


class VerificationContextProof(VerificationPayload):
    source_job_id: int = Field(gt=0)
    version: int = Field(default=1, ge=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class VerificationItemUpdateSubmission(VerificationPayload):
    status: str = Field(pattern=r"^(pending|completed)$")
    context: VerificationTask
    context_proof: VerificationContextProof


class VerificationItemJobSubmission(VerificationItemUpdateSubmission):
    item_id: str = Field(min_length=1, max_length=128)


class VerificationTaskOperationSubmission(VerificationPayload):
    context: VerificationTask
    context_proof: VerificationContextProof


class VerificationActionSubmission(VerificationTaskOperationSubmission):
    action: str


class VerificationAction(str, Enum):
    COMPLETE = "complete"
    SUPPLEMENT = "supplement"
    SUBMIT = "submit"
    APPROVAL_SUBMIT = "approval-submit"
