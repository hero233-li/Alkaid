from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkflowInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str = Field(min_length=1, max_length=500)


class WorkflowOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    normalized_value: str | None = None


class WorkflowContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    input: WorkflowInput
    output: WorkflowOutput = Field(default_factory=WorkflowOutput)

    def with_normalized_value(self, value: str) -> "WorkflowContext":
        return self.model_copy(update={"output": WorkflowOutput(normalized_value=value)})


class WorkflowStartRequest(BaseModel):
    input: WorkflowInput
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class WorkflowStatusValue(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WorkflowAcceptedResponse(BaseModel):
    workflow_id: UUID
    status: WorkflowStatusValue
    created: bool


class WorkflowStatusResponse(BaseModel):
    workflow_id: UUID
    status: WorkflowStatusValue
    current_step: str
    context: WorkflowContext
    error: str | None
    created_at: datetime
    updated_at: datetime
