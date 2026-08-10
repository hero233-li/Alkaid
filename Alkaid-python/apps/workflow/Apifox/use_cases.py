from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from apps.workflow.Apifox.integration import execute_workbench_http
from apps.workflow.Apifox.models import WorkbenchHistory, WorkbenchPackage, WorkbenchPackageRequest
from apps.workflow.Apifox.saz import parse_saz
from apps.workflow.Apifox.schemas import WorkbenchRequest
from apps.workflow.Apifox.services import (
    display_name,
    endpoint_key,
    normalize_request,
    validate_workbench_target,
)


@dataclass(frozen=True)
class WorkbenchExecutionOutcome:
    success: bool
    status_code: int
    duration_ms: int
    headers: dict[str, list[str]]
    body: str
    error_message: str | None
    history_id: int

    def as_api_result(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "statusCode": self.status_code,
            "durationMs": self.duration_ms,
            "headers": self.headers,
            "body": self.body,
            "errorMessage": self.error_message,
            "historyId": self.history_id,
        }


@transaction.atomic
def import_saz_package(upload: UploadedFile) -> WorkbenchPackage:
    if upload.size > settings.WORKBENCH_MAX_UPLOAD_BYTES:
        raise ValueError(
            f"上传文件 {upload.name} 超过上限 {settings.WORKBENCH_MAX_UPLOAD_BYTES} bytes"
        )
    if not upload.name.lower().endswith(".saz"):
        raise ValueError("请选择 Fiddler 导出的 .saz 文件")
    parsed = parse_saz(upload.read())
    source_filename = upload.name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    package_name = source_filename.rsplit(".", 1)[0].strip() or "Fiddler 接口包"
    package = WorkbenchPackage.objects.create(
        name=package_name[:255],
        source_filename=source_filename,
    )
    WorkbenchPackageRequest.objects.bulk_create(
        [
            WorkbenchPackageRequest(
                package=package,
                position=item.position,
                name=item.name,
                method=item.method,
                url=item.url,
                request_payload=item.request_payload,
                response_status=item.response_status,
                response_headers=item.response_headers,
                response_body=item.response_body,
            )
            for item in parsed
        ]
    )
    return WorkbenchPackage.objects.prefetch_related("requests").get(pk=package.pk)


def execute_workbench_request(
    submission: WorkbenchRequest,
    uploads: Mapping[str, UploadedFile] | None = None,
    *,
    transport: object | None = None,
) -> WorkbenchExecutionOutcome:
    started = time.monotonic()
    normalized, request_arguments = normalize_request(
        submission,
        uploads,
        resolve_dns=transport is None,
    )
    result = execute_workbench_http(
        method=normalized.method,
        url=normalized.url,
        headers=normalized.headers,
        request_arguments=request_arguments,
        timeout_seconds=normalized.timeoutSeconds,
        max_response_chars=settings.WORKBENCH_MAX_RESPONSE_CHARS,
        transport=transport,
    )
    for location in result.headers.get("location", []):
        validate_workbench_target(urljoin(normalized.url, location), resolve_dns=transport is None)

    duration_ms = round((time.monotonic() - started) * 1000)
    history_defaults = {
        "method": normalized.method,
        "url": normalized.url,
        "request_headers": normalized.headers,
        "request_payload": normalized.model_dump(mode="json"),
        "response_status": result.status_code,
        "duration_ms": duration_ms,
        "success": result.success,
        "error_message": result.error_message,
        "response_headers": result.headers,
        "response_body": result.body,
    }
    history, created = WorkbenchHistory.objects.get_or_create(
        endpoint_key=endpoint_key(normalized.method, normalized.url),
        defaults={
            "name": display_name(normalized.method, normalized.url),
            **history_defaults,
        },
    )
    if not created:
        for field, value in history_defaults.items():
            setattr(history, field, value)
        history.save(update_fields=[*history_defaults, "updated_at"])
    return WorkbenchExecutionOutcome(
        success=result.success,
        status_code=result.status_code or 0,
        duration_ms=duration_ms,
        headers=result.headers,
        body=result.body,
        error_message=result.error_message or None,
        history_id=history.id,
    )
