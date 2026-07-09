import json
import logging
import time
import uuid
from collections.abc import Callable, Mapping
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from apps.integrations.contracts import BusinessResponseError, HttpResult, ResponseModel

logger = logging.getLogger(__name__)


class HttpCallObserver(Protocol):
    def started(
        self,
        *,
        method: str,
        path: str,
        headers: Mapping[str, str],
        request_body: Any,
    ) -> object: ...

    def finished(
        self,
        handle: object,
        *,
        status_code: int | None,
        headers: Mapping[str, str],
        response_body: Any,
        duration_ms: int,
        error: Exception | None,
    ) -> None: ...


class HttpClientConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str
    token: str | None = None
    timeout_seconds: float = Field(default=10, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)


class ExternalServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HttpClient:
    retryable_statuses = {502, 503, 504}

    def __init__(
        self,
        config: HttpClientConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"Accept": "application/json"}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        self.config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers=headers,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        response_model: type[ResponseModel],
        body: BaseModel | None = None,
        form_data: Mapping[str, Any] | None = None,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        workflow_id: str | None = None,
        observer: HttpCallObserver | None = None,
        response_validator: Callable[[ResponseModel], None] | None = None,
    ) -> ResponseModel:
        return self.request_detailed(
            method,
            path,
            response_model=response_model,
            body=body,
            form_data=form_data,
            params=params,
            headers=headers,
            workflow_id=workflow_id,
            observer=observer,
            response_validator=response_validator,
        ).data

    def request_detailed(
        self,
        method: str,
        path: str,
        *,
        response_model: type[ResponseModel],
        body: BaseModel | None = None,
        form_data: Mapping[str, Any] | None = None,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        workflow_id: str | None = None,
        observer: HttpCallObserver | None = None,
        response_validator: Callable[[ResponseModel], None] | None = None,
    ) -> HttpResult[ResponseModel]:
        if body is not None and form_data is not None:
            raise ValueError("body 和 form_data 不能同时传递")
        trace_id = workflow_id or str(uuid.uuid4())
        started = time.monotonic()
        response: httpx.Response | None = None
        response_handle: object | None = None
        attempt_started = started
        request_json = body.model_dump(mode="json", exclude_none=True) if body else None
        request_form = _serialize_form(form_data) if form_data is not None else None
        audit_body = (
            {"query": dict(params or {}), "form": dict(form_data or {})}
            if form_data is not None
            else {"query": dict(params or {}), "body": request_json}
        )
        request_headers = dict(self._client.headers)
        request_headers.update(headers or {})
        request_headers["X-Trace-ID"] = trace_id

        for attempt in range(self.config.max_retries + 1):
            attempt_started = time.monotonic()
            response_handle = (
                observer.started(
                    method=method,
                    path=path,
                    headers=request_headers,
                    request_body=audit_body,
                )
                if observer
                else None
            )
            try:
                request_arguments: dict[str, Any] = {
                    "params": params,
                    "headers": request_headers,
                }
                if request_form is not None:
                    request_arguments["data"] = request_form
                else:
                    request_arguments["json"] = request_json
                response = self._client.request(method, path, **request_arguments)
                if response.status_code not in self.retryable_statuses:
                    break
                if observer and response_handle is not None:
                    observer.finished(
                        response_handle,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        response_body=_response_body(response),
                        duration_ms=round((time.monotonic() - attempt_started) * 1000),
                        error=ExternalServiceError(
                            "external service temporarily unavailable",
                            status_code=response.status_code,
                        ),
                    )
                    response_handle = None
            except httpx.TransportError as exc:
                if observer and response_handle is not None:
                    observer.finished(
                        response_handle,
                        status_code=None,
                        headers={},
                        response_body=None,
                        duration_ms=round((time.monotonic() - attempt_started) * 1000),
                        error=exc,
                    )
                    response_handle = None
                if attempt == self.config.max_retries:
                    self._log(method, path, trace_id, started, None, attempt + 1)
                    raise ExternalServiceError("external service transport error") from exc
            if attempt < self.config.max_retries:
                time.sleep(0.1 * (2**attempt))

        if response is None:
            raise ExternalServiceError("external service returned no response")
        self._log(method, path, trace_id, started, response.status_code, attempt + 1)
        try:
            response.raise_for_status()
            result = response_model.model_validate(response.json())
            if response_validator:
                response_validator(result)
        except httpx.HTTPStatusError as exc:
            if observer and response_handle is not None:
                observer.finished(
                    response_handle,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    response_body=_response_body(response),
                    duration_ms=round((time.monotonic() - attempt_started) * 1000),
                    error=exc,
                )
            raise ExternalServiceError(
                "external service rejected the request", status_code=response.status_code
            ) from exc
        except (ValueError, TypeError) as exc:
            if observer and response_handle is not None:
                observer.finished(
                    response_handle,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    response_body=_response_body(response),
                    duration_ms=round((time.monotonic() - attempt_started) * 1000),
                    error=exc,
                )
            raise ExternalServiceError(
                "external service returned an invalid response", status_code=response.status_code
            ) from exc
        except BusinessResponseError as exc:
            if observer and response_handle is not None:
                observer.finished(
                    response_handle,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    response_body=_response_body(response),
                    duration_ms=round((time.monotonic() - attempt_started) * 1000),
                    error=exc,
                )
            raise
        if observer and response_handle is not None:
            observer.finished(
                response_handle,
                status_code=response.status_code,
                headers=dict(response.headers),
                response_body=_response_body(response),
                duration_ms=round((time.monotonic() - attempt_started) * 1000),
                error=None,
            )
        return HttpResult(
            data=result,
            status_code=response.status_code,
            headers=dict(response.headers),
            body=_response_body(response),
        )

    @staticmethod
    def _log(
        method: str,
        path: str,
        trace_id: str,
        started: float,
        status_code: int | None,
        attempts: int,
    ) -> None:
        logger.info(
            "external_http_request",
            extra={
                "method": method.upper(),
                "path": path,
                "trace_id": trace_id,
                "status_code": status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "attempts": attempts,
            },
        )


def _response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def _serialize_form(form_data: Mapping[str, Any] | None) -> dict[str, str] | None:
    if form_data is None:
        return None
    serialized: dict[str, str] = {}
    for name, value in form_data.items():
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple)):
            serialized[name] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        elif isinstance(value, bool):
            serialized[name] = "true" if value else "false"
        else:
            serialized[name] = str(value)
    return serialized
