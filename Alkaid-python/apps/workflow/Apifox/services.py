from __future__ import annotations

import hashlib
import ipaddress
import socket
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.workflow.Apifox.models import WorkbenchHistory, WorkbenchPackage, WorkbenchPackageRequest
from apps.workflow.Apifox.schemas import WorkbenchRequest

RESTRICTED_HEADERS = {
    "connection",
    "content-length",
    "host",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def validate_workbench_target(url: str, *, resolve_dns: bool = True) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.username or parsed.password:
        raise ValueError("接口工作台 URL 禁止包含用户名或密码")
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("接口工作台仅支持有效的 HTTP/HTTPS URL")
    allowed_hosts = set(settings.WORKBENCH_ALLOWED_HOSTS)
    if "*" in allowed_hosts:
        return
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("接口工作台禁止访问内部或保留地址：localhost")
    if host not in allowed_hosts:
        raise ValueError(f"接口工作台目标 Host 未获允许：{host}")
    addresses: set[str] = set()
    try:
        addresses.add(str(ipaddress.ip_address(host)))
    except ValueError:
        if resolve_dns:
            addresses.update(item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443))
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_loopback
            or ip.is_link_local
            or ip.is_private
            or ip.is_reserved
            or ip.is_unspecified
            or ip.is_multicast
            or address == "169.254.169.254"
        ):
            raise ValueError(f"接口工作台禁止访问内部或保留地址：{address}")


def display_name(method: str, url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{method} {parsed.hostname or ''}{path}"[:255]


def endpoint_key(method: str, url: str) -> str:
    """Return the stable identity of one executable Apifox endpoint."""
    identity = f"{method.upper()}\n{url}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def request_arguments(
    submission: WorkbenchRequest,
    uploads: Mapping[str, UploadedFile],
) -> tuple[dict[str, Any], list[UploadedFile]]:
    arguments: dict[str, Any] = {"headers": submission.headers}
    opened_uploads: list[UploadedFile] = []
    fields = [field for field in submission.formFields if field.enabled]
    form_data: dict[str, list[str]] = {}
    for field in fields:
        if field.type == "text":
            form_data.setdefault(field.name, []).append(field.value)
    if submission.bodyMode == "form-urlencoded":
        arguments["data"] = form_data
    elif submission.bodyMode == "form-data":
        arguments["data"] = form_data
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


def normalize_request(
    submission: WorkbenchRequest,
    uploads: Mapping[str, UploadedFile] | None = None,
    *,
    resolve_dns: bool = True,
) -> tuple[WorkbenchRequest, dict[str, Any]]:
    validate_workbench_target(submission.url, resolve_dns=resolve_dns)
    safe_headers = {
        name: value
        for name, value in submission.headers.items()
        if name.lower() not in RESTRICTED_HEADERS
    }
    for upload in (uploads or {}).values():
        if upload.size > settings.WORKBENCH_MAX_UPLOAD_BYTES:
            raise ValueError(
                f"上传文件 {upload.name} 超过上限 {settings.WORKBENCH_MAX_UPLOAD_BYTES} bytes"
            )
    normalized = submission.model_copy(update={"headers": safe_headers})
    arguments, _ = request_arguments(normalized, uploads or {})
    return normalized, {name: value for name, value in arguments.items() if name != "headers"}


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
        "createdAt": history.updated_at.isoformat(),
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


def serialize_package(package: WorkbenchPackage) -> dict[str, Any]:
    requests = list(package.requests.all())
    return {
        "id": package.id,
        "name": package.name,
        "sourceFilename": package.source_filename,
        "requestCount": len(requests),
        "createdAt": package.created_at.isoformat(),
        "requests": [serialize_package_request(item) for item in requests],
    }


def serialize_package_request(item: WorkbenchPackageRequest) -> dict[str, Any]:
    return {
        "id": item.id,
        "packageId": item.package_id,
        "position": item.position,
        "name": item.name,
        "method": item.method,
        "url": item.url,
        "responseStatus": item.response_status,
    }


def serialize_package_request_detail(item: WorkbenchPackageRequest) -> dict[str, Any]:
    data = serialize_package_request(item)
    data.update(
        {
            "requestPayload": item.request_payload,
            "response": {
                "success": bool(item.response_status and 200 <= item.response_status < 400),
                "statusCode": item.response_status or 0,
                "durationMs": 0,
                "headers": item.response_headers,
                "body": item.response_body,
                "errorMessage": None,
            },
        }
    )
    return data
