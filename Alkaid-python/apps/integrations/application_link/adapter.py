"""All HTTP and external wire contracts for application-link generation."""

from __future__ import annotations

import json
from typing import Any

import httpx
from django.conf import settings

from apps.integrations.application_link.api import (
    CREATE_APPLICATION,
    CREATE_DYNAMIC_LINKS,
    CREATE_SUN_CODE_LINKS,
)
from apps.integrations.application_link.models import (
    ApplicationLinks,
    ApplicationReference,
    CreateApplicationRequest,
    GenerateLinksRequest,
)
from apps.integrations.auth import TokenManager
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


class ApplicationLinkAdapter:
    """Per-Job adapter that records every external call in ``JobApiCall``."""

    def __init__(self, job: Job) -> None:
        self.job = job
        self._client: HttpClient | None = None
        self._executor: EndpointExecutor | None = None

    def __enter__(self) -> ApplicationLinkAdapter:
        self._client = _create_client()
        self._executor = EndpointExecutor(self._client, TokenManager({}))
        return self

    def __exit__(self, *_: object) -> None:
        if self._client:
            self._client.close()
        self._client = None
        self._executor = None

    def create_application(self, request: CreateApplicationRequest) -> ApplicationReference:
        response = self._execute("application_link.create_application", CREATE_APPLICATION, request)
        return response.data

    def generate_links(
        self,
        request: GenerateLinksRequest,
        *,
        category: object,
    ) -> ApplicationLinks:
        category_value = getattr(category, "value", category)
        endpoint = (
            CREATE_DYNAMIC_LINKS if category_value == "动态链接" else CREATE_SUN_CODE_LINKS
        )
        response = self._execute("application_link.generate_links", endpoint, request)
        return response.data

    def _execute(self, step: str, endpoint: object, body: object):
        if self._executor is None:
            raise RuntimeError("ApplicationLinkAdapter 必须在 with 块中使用")
        return self._executor.execute(
            endpoint,  # type: ignore[arg-type]
            body=body,  # type: ignore[arg-type]
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(self.job, step=step),
        )


def _create_client() -> HttpClient:
    if settings.APPLICATION_LINK_BASE_URL:
        return HttpClient(
            HttpClientConfig(
                base_url=settings.APPLICATION_LINK_BASE_URL,
                token=settings.APPLICATION_LINK_API_TOKEN or None,
            )
        )
    return _create_mock_client()


def _create_mock_client() -> HttpClient:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = _read_json(request)
        if request.url.path == "/applications":
            product = str(payload.get("product") or "unknown").replace(" ", "-")
            return httpx.Response(
                200,
                json={"code": "0000", "data": {"application_no": f"MOCK-LINK-{product}-001"}},
            )
        if request.url.path in {"/links/sun-code", "/links/dynamic"}:
            application_no = str(payload.get("application_no") or "MOCK-LINK-UNKNOWN")
            path_kind = "dynamic" if request.url.path.endswith("dynamic") else "sun-code"
            return httpx.Response(
                200,
                json={
                    "code": "0000",
                    "data": {
                        "internal_url": f"https://internal.example.local/apply/{application_no}",
                        "external_url": f"https://apply.example.local/{path_kind}/{application_no}",
                    },
                },
            )
        return httpx.Response(404, json={"code": "NOT_FOUND"})

    return HttpClient(
        HttpClientConfig(base_url="https://mock-application-link.local", max_retries=0),
        transport=httpx.MockTransport(handler),
    )


def _read_json(request: httpx.Request) -> dict[str, Any]:
    try:
        value = json.loads(request.content.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}
