from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx


@dataclass(frozen=True)
class WorkbenchHttpResult:
    status_code: int | None
    headers: dict[str, list[str]]
    body: str
    success: bool
    error_message: str


def _response_headers(response: httpx.Response) -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    for name, value in response.headers.multi_items():
        headers.setdefault(name, []).append(value)
    return headers


def execute_workbench_http(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    request_arguments: dict[str, Any],
    timeout_seconds: int,
    max_response_chars: int,
    transport: object | None = None,
) -> WorkbenchHttpResult:
    try:
        with httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=cast(httpx.BaseTransport | None, transport),
        ) as client:
            response = client.request(method, url, headers=headers, **request_arguments)
    except httpx.HTTPError as exc:
        return WorkbenchHttpResult(
            status_code=None,
            headers={},
            body="",
            success=False,
            error_message=f"{type(exc).__name__}: {exc}",
        )
    return WorkbenchHttpResult(
        status_code=response.status_code,
        headers=_response_headers(response),
        body=response.text[:max_response_chars],
        success=response.is_success,
        error_message="",
    )
