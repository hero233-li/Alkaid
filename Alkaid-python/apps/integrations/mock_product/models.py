from typing import Any

from pydantic import BaseModel, Field, RootModel


class LoginRequest(BaseModel):
    product: str


class TokenData(BaseModel):
    token: str


class LoginResponse(BaseModel):
    data: TokenData


class ProductCheckRequest(BaseModel):
    product: str
    customerType: str
    switchName: str
    switchEnabled: bool


class OperationResponse(BaseModel):
    code: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


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
