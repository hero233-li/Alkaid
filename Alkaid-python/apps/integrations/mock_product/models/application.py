from typing import Any

from pydantic import BaseModel, RootModel


class ProductCheckRequest(BaseModel):
    product: str
    customerType: str
    switchName: str
    switchEnabled: bool


class RotateTokenRequest(BaseModel):
    reason: str


class ProductSubmitRequest(BaseModel):
    product: str
    payload: dict[str, Any]


class MappedPayloadRequest(RootModel[dict[str, Any]]):
    pass


class FixedTokenRequest(BaseModel):
    jobId: int
    product: str


class RequestHead(BaseModel):
    traceno: str
    starttime: str
    product: str


class ProductCheckInput(BaseModel):
    product: str
    customer_type: str
    switch_name: str
    switch_enabled: bool
    product_type: str


class ProductSubmissionInput(BaseModel):
    product: str
    environment: str
    product_type: str
    organization_code: str
    customer_name: str
    certificate_no: str
    phone: str
    customer_type: str
    outlet_code: str
    application_method: str
    risk: dict[str, bool]
    dynamic_term: str | None = None
    dynamic_amount: str | None = None
    extra_reason: str | None = None
    order_no: str | None = None
