from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class RetryMode(str, Enum):
    NEVER = "never"
    CONNECT_ONLY = "connect_only"
    IDEMPOTENT = "idempotent"


class IntegrationObserver(Protocol):
    def request_started(
        self,
        *,
        step: str,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Any,
    ) -> object: ...

    def request_finished(
        self,
        handle: object,
        *,
        status_code: int | None,
        headers: Mapping[str, str],
        body: Any,
        duration_ms: int,
        error: Exception | None,
    ) -> None: ...

    def diagnostic(
        self,
        *,
        step: str,
        title: str,
        content: Any,
        level: str = "INFO",
    ) -> None: ...


class BusinessResponseError(RuntimeError):
    pass


@dataclass(frozen=True)
class EndpointSpec(Generic[ResponseModel]):
    operation_id: str
    method: str
    path: str
    response_model: type[ResponseModel]
    retry_mode: RetryMode = RetryMode.NEVER


@dataclass(frozen=True)
class HttpResult(Generic[ResponseModel]):
    data: ResponseModel
    status_code: int
    headers: dict[str, str]
    body: Any
