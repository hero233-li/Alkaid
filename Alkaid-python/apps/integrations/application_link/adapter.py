"""All HTTP and external wire contracts for application-link generation."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.integrations.application_link.api import (
    CREATE_APPLICATION,
    CREATE_DYNAMIC_LINKS,
    CREATE_SUN_CODE_LINKS,
)
from apps.integrations.application_link.mock_transport import (
    create_application_link_mock_transport,
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
        endpoint = CREATE_DYNAMIC_LINKS if category_value == "动态链接" else CREATE_SUN_CODE_LINKS
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
    if settings.EXTERNAL_SYSTEM_MODE == "mock":
        return _create_mock_client()
    if settings.APPLICATION_LINK_BASE_URL:
        return HttpClient(
            HttpClientConfig(
                base_url=settings.APPLICATION_LINK_BASE_URL,
                token=settings.APPLICATION_LINK_API_TOKEN or None,
                timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
                connect_timeout_seconds=settings.HTTP_CONNECT_TIMEOUT_SECONDS,
                write_timeout_seconds=settings.HTTP_WRITE_TIMEOUT_SECONDS,
                pool_timeout_seconds=settings.HTTP_POOL_TIMEOUT_SECONDS,
                max_retries=settings.HTTP_MAX_RETRIES,
                retry_backoff_seconds=settings.HTTP_RETRY_BACKOFF_SECONDS,
                retry_max_backoff_seconds=settings.HTTP_RETRY_MAX_BACKOFF_SECONDS,
            )
        )
    raise ImproperlyConfigured("APPLICATION_LINK_BASE_URL 未配置")


def _create_mock_client() -> HttpClient:
    return HttpClient(
        HttpClientConfig(base_url="https://mock-application-link.local", max_retries=0),
        transport=create_application_link_mock_transport(),
    )
