import logging
import time
import uuid
from collections.abc import Callable, Mapping
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from apps.integrations.contracts import BusinessResponseError, HttpResult, ResponseModel
from apps.integrations.http_payload import response_body, serialize_form
from apps.integrations.retry_policy import retry_delay

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
    connect_timeout_seconds: float | None = Field(default=None, gt=0)
    write_timeout_seconds: float | None = Field(default=None, gt=0)
    pool_timeout_seconds: float | None = Field(default=None, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=0.2, ge=0)
    retry_max_backoff_seconds: float = Field(default=5, gt=0)


class ExternalServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HttpClient:
    retryable_statuses = {429, 502, 503, 504}

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
            timeout=httpx.Timeout(
                config.timeout_seconds,
                connect=config.connect_timeout_seconds or config.timeout_seconds,
                write=config.write_timeout_seconds or config.timeout_seconds,
                pool=config.pool_timeout_seconds or config.timeout_seconds,
            ),
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
        trace_id: str | None = None,
        observer: HttpCallObserver | None = None,
        response_validator: Callable[[ResponseModel], None] | None = None,
        max_retries: int | None = None,
    ) -> ResponseModel:
        return self.request_detailed(
            method,
            path,
            response_model=response_model,
            body=body,
            form_data=form_data,
            params=params,
            headers=headers,
            trace_id=trace_id,
            observer=observer,
            response_validator=response_validator,
            max_retries=max_retries,
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
        trace_id: str | None = None,
        observer: HttpCallObserver | None = None,
        response_validator: Callable[[ResponseModel], None] | None = None,
        max_retries: int | None = None,
    ) -> HttpResult[ResponseModel]:
        if body is not None and form_data is not None:
            raise ValueError("body 和 form_data 不能同时传递")
        trace_id = trace_id or str(uuid.uuid4())
        started = time.monotonic()
        response: httpx.Response | None = None
        response_handle: object | None = None
        attempt_started = started
        request_json = body.model_dump(mode="json", exclude_none=True) if body else None
        request_form = serialize_form(form_data) if form_data is not None else None
        audit_body = (
            {"query": dict(params or {}), "form": dict(form_data or {})}
            if form_data is not None
            else {"query": dict(params or {}), "body": request_json}
        )
        request_headers = dict(self._client.headers)
        request_headers.update(headers or {})
        request_headers["X-Trace-ID"] = trace_id
        request_retries = self.config.max_retries if max_retries is None else max_retries
        if request_retries < 0 or request_retries > 5:
            raise ValueError("max_retries 必须在 0 到 5 之间")

        for attempt in range(request_retries + 1):
            attempt_started = time.monotonic()
            response = None
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
                        response_body=response_body(response),
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
                if attempt == request_retries:
                    self._log(method, path, trace_id, started, None, attempt + 1)
                    raise ExternalServiceError("external service transport error") from exc
            if attempt < request_retries:
                time.sleep(self._retry_delay(attempt, response))

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
                    response_body=response_body(response),
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
                    response_body=response_body(response),
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
                    response_body=response_body(response),
                    duration_ms=round((time.monotonic() - attempt_started) * 1000),
                    error=exc,
                )
            raise
        if observer and response_handle is not None:
            observer.finished(
                response_handle,
                status_code=response.status_code,
                headers=dict(response.headers),
                response_body=response_body(response),
                duration_ms=round((time.monotonic() - attempt_started) * 1000),
                error=None,
            )
        return HttpResult(
            data=result,
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response_body(response),
        )

    def _retry_delay(self, attempt: int, response: httpx.Response | None) -> float:
        return retry_delay(
            attempt,
            response,
            backoff_seconds=self.config.retry_backoff_seconds,
            max_backoff_seconds=self.config.retry_max_backoff_seconds,
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
