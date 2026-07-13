from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class WireModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class SearchVerificationTaskRequest(WireModel):
    environment: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=128)
    contract_no: str = Field(min_length=1, max_length=128)


class VerificationItemUpdateRequest(WireModel):
    status: Literal["pending", "completed"]
    context: "VerificationTask"


class VerificationActionRequest(WireModel):
    action: Literal["complete", "supplement", "submit", "approval-submit"]
    context: "VerificationTask"


class VerificationItem(WireModel):
    id: str
    title: str
    status: Literal["pending", "completed"]


class VerificationTask(WireModel):
    id: str
    contract_no: str
    ownership_status: Literal["unclaimed", "claimed"]
    task_status: str
    node: str
    teller_no: str
    organization_no: str
    product_name: str
    items: tuple[VerificationItem, ...]


class VerificationTaskOperationRequest(WireModel):
    context: VerificationTask


class VerificationTaskResponse(WireModel):
    code: str
    message: str
    data: VerificationTask | None
