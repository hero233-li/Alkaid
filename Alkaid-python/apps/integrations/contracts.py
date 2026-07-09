from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class TokenSource(str, Enum):
    RESPONSE_BODY = "response_body"
    RESPONSE_HEADER = "response_header"


class BusinessResponseError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthSpec:
    provider: str
    header: str = "Authorization"
    prefix: str = "Bearer "


@dataclass(frozen=True)
class TokenUpdateSpec:
    provider: str
    source: TokenSource
    path: str


@dataclass(frozen=True)
class EndpointSpec(Generic[ResponseModel]):
    operation_id: str
    method: str
    path: str
    response_model: type[ResponseModel]
    auth: AuthSpec | None = None
    token_update: TokenUpdateSpec | None = None
    success_path: str | None = None
    success_values: tuple[Any, ...] = ()


@dataclass(frozen=True)
class HttpResult(Generic[ResponseModel]):
    data: ResponseModel
    status_code: int
    headers: dict[str, str]
    body: Any
