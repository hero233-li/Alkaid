from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.integrations.workbench import execute_workbench_http
from apps.workbench.models import WorkbenchHistory
from apps.workbench.schemas import WorkbenchRequest

RESTRICTED_HEADERS = {"connection", "content-length", "host", "transfer-encoding"}


def _display_name(method: str, url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{method} {parsed.hostname or ''}{path}"[:255]


def _request_arguments(
    submission: WorkbenchRequest,
    uploads: Mapping[str, UploadedFile],
) -> tuple[dict[str, Any], list[UploadedFile]]:
    arguments: dict[str, Any] = {"headers": submission.headers}
    opened_uploads: list[UploadedFile] = []
    fields = [field for field in submission.formFields if field.enabled]
    if submission.bodyMode == "form-urlencoded":
        arguments["data"] = [(field.name, field.value) for field in fields if field.type == "text"]
    elif submission.bodyMode == "form-data":
        arguments["data"] = [(field.name, field.value) for field in fields if field.type == "text"]
        files: list[tuple[str, tuple[str, UploadedFile, str]]] = []
        for field in fields:
            if field.type != "file" or not field.filePartName:
                continue
            upload = uploads.get(field.filePartName)
            if upload is None:
                continue
            opened_uploads.append(upload)
            files.append(
                (
                    field.name,
                    (upload.name, upload, upload.content_type or "application/octet-stream"),
                )
            )
        arguments["files"] = files
    elif submission.bodyMode != "none" and submission.body:
        arguments["content"] = submission.body.encode()
    return arguments, opened_uploads


def execute_request(
    submission: WorkbenchRequest,
    uploads: Mapping[str, UploadedFile] | None = None,
    *,
    transport: object | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    safe_headers = {
        name: value
        for name, value in submission.headers.items()
        if name.lower() not in RESTRICTED_HEADERS
    }
    normalized = submission.model_copy(update={"headers": safe_headers})
    arguments, _ = _request_arguments(normalized, uploads or {})
    result = execute_workbench_http(
        method=normalized.method,
        url=normalized.url,
        headers=safe_headers,
        request_arguments={name: value for name, value in arguments.items() if name != "headers"},
        timeout_seconds=normalized.timeoutSeconds,
        max_response_chars=settings.WORKBENCH_MAX_RESPONSE_CHARS,
        transport=transport,
    )

    duration_ms = round((time.monotonic() - started) * 1000)
    history = WorkbenchHistory.objects.create(
        name=_display_name(normalized.method, normalized.url),
        method=normalized.method,
        url=normalized.url,
        request_headers=safe_headers,
        request_payload=normalized.model_dump(mode="json"),
        response_status=result.status_code,
        duration_ms=duration_ms,
        success=result.success,
        error_message=result.error_message,
        response_headers=result.headers,
        response_body=result.body,
    )
    return {
        "success": result.success,
        "statusCode": result.status_code or 0,
        "durationMs": duration_ms,
        "headers": result.headers,
        "body": result.body,
        "errorMessage": result.error_message or None,
        "historyId": history.id,
    }


def serialize_history(history: WorkbenchHistory, *, detail: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": history.id,
        "name": history.name,
        "method": history.method,
        "url": history.url,
        "responseStatus": history.response_status,
        "durationMs": history.duration_ms,
        "success": history.success,
        "errorMessage": history.error_message or None,
        "createdAt": history.created_at.isoformat(),
    }
    if detail:
        data.update(
            {
                "requestHeaders": history.request_headers,
                "requestPayload": history.request_payload,
                "responseHeaders": history.response_headers,
                "responseBody": history.response_body,
            }
        )
    return data
