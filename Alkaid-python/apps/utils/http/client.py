import json
import logging
import random
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apps.utils.http.contracts import (
    BusinessResponseError,
    HttpResult,
    IntegrationObserver,
    ResponseModel,
    RetryMode,
)

logger = logging.getLogger(__name__)


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
    follow_redirects: bool = False
    max_response_bytes: int = Field(default=5 * 1024 * 1024, gt=0)


class ExternalServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class HttpFile:
    """An in-memory file part used in a multipart request."""

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


class HttpClient:
    retryable_statuses = {429, 502, 503, 504}

    def __init__(
        self,
        config: HttpClientConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        headers = {"Accept": "application/json"}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        self.config = config
        self._random_uniform = random_uniform
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
            follow_redirects=config.follow_redirects,
        )

    @property
    def cookie_names(self) -> tuple[str, ...]:
        return tuple(sorted({cookie.name for cookie in self._client.cookies.jar}))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def open_url(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        trace_id: str | None = None,
        observer: IntegrationObserver | None = None,
        step: str | None = None,
    ) -> httpx.Response:
        """Open an HTML/page URL while preserving this client's cookie jar."""

        observer_step = _validate_observer_step(observer, step)
        trace_id = trace_id or str(uuid.uuid4())
        started = time.monotonic()
        request_headers = dict(self._client.headers)
        request_headers.update(headers or {})
        request_headers["X-Trace-ID"] = trace_id
        audit_url = str(self._client.base_url.join(url).copy_merge_params(params or {}))
        response_handle = (
            observer.request_started(
                step=observer_step,
                method=method,
                url=audit_url,
                headers=request_headers,
                body={"query": dict(params or {})},
            )
            if observer
            else None
        )
        response: httpx.Response | None = None
        try:
            response = self._client.request(
                method,
                url,
                params=params,
                headers=request_headers,
            )
            if response.status_code >= 400:
                response.raise_for_status()
        except httpx.TransportError as exc:
            if observer and response_handle is not None:
                observer.request_finished(
                    response_handle,
                    status_code=None,
                    headers={},
                    body=None,
                    duration_ms=round((time.monotonic() - started) * 1000),
                    error=exc,
                )
            self._log(method, audit_url, trace_id, started, None, 1)
            raise ExternalServiceError("external service transport error") from exc
        except httpx.HTTPStatusError as exc:
            if observer and response_handle is not None and response is not None:
                observer.request_finished(
                    response_handle,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=_raw_response_summary(response),
                    duration_ms=round((time.monotonic() - started) * 1000),
                    error=exc,
                )
            self._log(
                method,
                audit_url,
                trace_id,
                started,
                response.status_code if response is not None else None,
                1,
            )
            raise ExternalServiceError(
                "external service rejected the request",
                status_code=response.status_code if response is not None else None,
            ) from exc

        self._log(method, audit_url, trace_id, started, response.status_code, 1)
        if observer and response_handle is not None:
            observer.request_finished(
                response_handle,
                status_code=response.status_code,
                headers=dict(response.headers),
                body=_raw_response_summary(response),
                duration_ms=round((time.monotonic() - started) * 1000),
                error=None,
            )
        return response

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
        observer: IntegrationObserver | None = None,
        step: str | None = None,
        response_validator: Callable[[Any], None] | None = None,
        max_retries: int | None = None,
        retry_mode: RetryMode = RetryMode.NEVER,
        files: Mapping[str, HttpFile] | None = None,
        raw_body: str | bytes | None = None,
        content_type: str | None = None,
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
            step=step,
            response_validator=response_validator,
            max_retries=max_retries,
            retry_mode=retry_mode,
            files=files,
            raw_body=raw_body,
            content_type=content_type,
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
        observer: IntegrationObserver | None = None,
        step: str | None = None,
        response_validator: Callable[[Any], None] | None = None,
        max_retries: int | None = None,
        retry_mode: RetryMode = RetryMode.NEVER,
        files: Mapping[str, HttpFile] | None = None,
        raw_body: str | bytes | None = None,
        content_type: str | None = None,
    ) -> HttpResult[ResponseModel]:
        observer_step = _validate_observer_step(observer, step)
        if body is not None and form_data is not None:
            raise ValueError("body 和 form_data 不能同时传递")
        if raw_body is not None and (body is not None or form_data is not None or files):
            raise ValueError("raw_body 不能和 body、form_data 或 files 同时传递")
        if files and body is not None:
            raise ValueError("files 不能和 JSON body 同时传递")
        if content_type is not None and raw_body is None:
            raise ValueError("content_type 只能和 raw_body 一起传递")
        trace_id = trace_id or str(uuid.uuid4())
        started = time.monotonic()
        response: httpx.Response | None = None
        response_handle: object | None = None
        attempt_started = started
        request_json = body.model_dump(mode="json", exclude_none=True) if body else None
        request_form = _serialize_form(form_data) if form_data is not None else None
        if files:
            audit_body = {
                "query": dict(params or {}),
                "form": dict(form_data or {}),
                "files": {
                    name: {
                        "filename": file.filename,
                        "contentType": file.content_type,
                        "size": len(file.content),
                    }
                    for name, file in files.items()
                },
            }
        elif raw_body is not None:
            raw_body_size = len(raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body)
            audit_body = {
                "query": dict(params or {}),
                "rawBody": {
                    "contentType": content_type,
                    "size": raw_body_size,
                },
            }
        elif form_data is not None:
            audit_body = {"query": dict(params or {}), "form": dict(form_data)}
        else:
            audit_body = {"query": dict(params or {}), "body": request_json}
        audit_url = str(self._client.base_url.join(path).copy_merge_params(params or {}))
        request_headers = dict(self._client.headers)
        request_headers.update(headers or {})
        request_headers["X-Trace-ID"] = trace_id
        if content_type and not any(name.lower() == "content-type" for name in request_headers):
            request_headers["Content-Type"] = content_type
        request_retries = self.config.max_retries if max_retries is None else max_retries
        if retry_mode == RetryMode.NEVER:
            request_retries = 0
        if request_retries < 0 or request_retries > 5:
            raise ValueError("max_retries 必须在 0 到 5 之间")

        for attempt in range(request_retries + 1):
            attempt_started = time.monotonic()
            response = None
            response_handle = (
                observer.request_started(
                    step=observer_step,
                    method=method,
                    url=audit_url,
                    headers=request_headers,
                    body=audit_body,
                )
                if observer
                else None
            )
            try:
                request_arguments: dict[str, Any] = {
                    "params": params,
                    "headers": request_headers,
                }
                if raw_body is not None:
                    request_arguments["content"] = raw_body
                elif files:
                    request_arguments["data"] = request_form or {}
                    request_arguments["files"] = _serialize_files(files)
                elif request_form is not None:
                    request_arguments["data"] = request_form
                else:
                    request_arguments["json"] = request_json
                response = self._client.request(method, path, **request_arguments)
                if (
                    retry_mode != RetryMode.IDEMPOTENT
                    or response.status_code not in self.retryable_statuses
                ):
                    break
                if observer and response_handle is not None:
                    observer.request_finished(
                        response_handle,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body=_response_body(response),
                        duration_ms=round((time.monotonic() - attempt_started) * 1000),
                        error=ExternalServiceError(
                            "external service temporarily unavailable",
                            status_code=response.status_code,
                        ),
                    )
                    response_handle = None
            except httpx.TransportError as exc:
                if observer and response_handle is not None:
                    observer.request_finished(
                        response_handle,
                        status_code=None,
                        headers={},
                        body=None,
                        duration_ms=round((time.monotonic() - attempt_started) * 1000),
                        error=exc,
                    )
                    response_handle = None
                retryable_transport = retry_mode == RetryMode.IDEMPOTENT or (
                    retry_mode == RetryMode.CONNECT_ONLY
                    and isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout))
                )
                if not retryable_transport or attempt == request_retries:
                    self._log(method, path, trace_id, started, None, attempt + 1)
                    raise ExternalServiceError("external service transport error") from exc
            if attempt < request_retries:
                time.sleep(self._retry_delay(attempt, response))

        if response is None:
            raise ExternalServiceError("external service returned no response")
        if len(response.content) > self.config.max_response_bytes:
            raise ExternalServiceError(
                f"外系统响应体超过上限 {self.config.max_response_bytes} bytes",
                status_code=response.status_code,
            )
        self._log(method, path, trace_id, started, response.status_code, attempt + 1)
        raw_response_body = _response_body_for_audit(response)
        try:
            response.raise_for_status()
            raw_response_body = _response_body(response)
            if response_validator:
                response_validator(raw_response_body)
            result = response_model.model_validate(raw_response_body)
        except httpx.HTTPStatusError as exc:
            if observer and response_handle is not None:
                observer.request_finished(
                    response_handle,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=raw_response_body,
                    duration_ms=round((time.monotonic() - attempt_started) * 1000),
                    error=exc,
                )
            raise ExternalServiceError(
                "external service rejected the request",
                status_code=response.status_code,
            ) from exc
        except ValidationError as exc:
            if observer and response_handle is not None:
                observer.request_finished(
                    response_handle,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=raw_response_body,
                    duration_ms=round((time.monotonic() - attempt_started) * 1000),
                    error=exc,
                )
            raise ExternalServiceError(
                _invalid_response_message(exc, raw_response_body),
                status_code=response.status_code,
            ) from exc
        except (ValueError, TypeError) as exc:
            if observer and response_handle is not None:
                observer.request_finished(
                    response_handle,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=raw_response_body,
                    duration_ms=round((time.monotonic() - attempt_started) * 1000),
                    error=exc,
                )
            raise ExternalServiceError(
                f"外系统响应无法解析：{type(exc).__name__}: {exc}",
                status_code=response.status_code,
            ) from exc
        except BusinessResponseError as exc:
            if observer and response_handle is not None:
                observer.request_finished(
                    response_handle,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=raw_response_body,
                    duration_ms=round((time.monotonic() - attempt_started) * 1000),
                    error=exc,
                )
            raise
        if observer and response_handle is not None:
            observer.request_finished(
                response_handle,
                status_code=response.status_code,
                headers=dict(response.headers),
                body=raw_response_body,
                duration_ms=round((time.monotonic() - attempt_started) * 1000),
                error=None,
            )
        return HttpResult(
            data=result,
            status_code=response.status_code,
            headers=dict(response.headers),
            body=raw_response_body,
        )

    def _retry_delay(self, attempt: int, response: httpx.Response | None) -> float:
        retry_after = _retry_after_seconds(response)
        if retry_after is not None:
            return min(retry_after, self.config.retry_max_backoff_seconds)
        exponential = self.config.retry_backoff_seconds * (2**attempt)
        delay = min(exponential, self.config.retry_max_backoff_seconds)
        return delay * self._random_uniform(0.8, 1.2)

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


def _validate_observer_step(
    observer: IntegrationObserver | None,
    step: str | None,
) -> str:
    normalized = (step or "").strip()
    if observer is not None and not normalized:
        raise ValueError("使用 observer 时必须提供 step")
    return normalized


def _invalid_response_message(
    error: ValidationError,
    response_body: Any,
) -> str:
    missing_fields: list[str] = []
    for item in error.errors():
        if item.get("type") != "missing":
            continue
        location = ".".join(str(part) for part in item.get("loc", ()))
        if location:
            missing_fields.append(location)

    if isinstance(response_body, Mapping):
        actual_fields = ", ".join(sorted(str(key) for key in response_body)) or "<空对象>"
    else:
        actual_fields = type(response_body).__name__

    missing_text = ", ".join(missing_fields) if missing_fields else str(error).splitlines()[0]
    return f"外系统响应结构不符合预期：缺少/错误字段={missing_text}；实际顶层字段={actual_fields}"


def _response_body(response: httpx.Response) -> Any:
    content_type = response.headers.get("Content-Type", "").lower()
    if "xml" in content_type:
        upper_content = response.content.upper()
        if b"<!DOCTYPE" in upper_content or b"<!ENTITY" in upper_content:
            raise ValueError("XML response must not contain DTD or entity declarations")
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise ValueError(f"invalid XML response: {exc}") from exc
        return _xml_element_value(root)
    try:
        return response.json()
    except ValueError:
        return response.text


def _response_body_for_audit(response: httpx.Response) -> Any:
    try:
        return _response_body(response)
    except (TypeError, ValueError):
        return response.text


def _xml_element_value(element: ElementTree.Element) -> Any:
    children = list(element)
    attributes = {_xml_name(name): value for name, value in element.attrib.items()}
    text = (element.text or "").strip()
    if not children and not attributes:
        return text

    result: dict[str, Any] = {f"@{name}": value for name, value in attributes.items()}
    for child in children:
        name = _xml_name(child.tag)
        value = _xml_element_value(child)
        existing = result.get(name)
        if existing is None:
            result[name] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            result[name] = [existing, value]
    if text:
        result["#text"] = text
    return result


def _xml_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _serialize_files(files: Mapping[str, HttpFile]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        (name, (file.filename, file.content, file.content_type)) for name, file in files.items()
    ]


def _raw_response_summary(response: httpx.Response) -> dict[str, Any]:
    return {
        "url": str(response.url),
        "contentType": response.headers.get("Content-Type"),
        "contentLength": len(response.content),
        "body": response.text,
        "redirects": [
            {
                "status": item.status_code,
                "url": str(item.url),
            }
            for item in response.history
        ],
    }


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


def _retry_after_seconds(response: httpx.Response | None) -> float | None:
    if response is None:
        return None
    value = response.headers.get("Retry-After", "").strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
