from datetime import datetime

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from apps.integrations.auth import FlowTokenProvider, StaticTokenProvider, TokenManager
from apps.integrations.contracts import EndpointSpec, ResponseModel
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.integrations.mock_product.api import FIXED_PROVIDER, FLOW_PROVIDER
from apps.integrations.mock_product.mock_transport import create_mock_product_transport
from apps.integrations.mock_product.models import RequestHead
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


class MockProductClient:
    """Shared HTTP, token and audit boundary for this external system."""

    def __init__(self, job: Job) -> None:
        self.job = job
        self._fixed_token = settings.MOCK_FIXED_SYSTEM_TOKEN
        self.tokens = TokenManager(
            {
                FLOW_PROVIDER: FlowTokenProvider(),
                FIXED_PROVIDER: StaticTokenProvider(self._fixed_token),
            }
        )
        self._http_client: HttpClient | None = None
        self._executor: EndpointExecutor | None = None

    def __enter__(self) -> "MockProductClient":
        self._http_client = create_product_http_client(self._fixed_token)
        self._executor = EndpointExecutor(self._http_client, self.tokens)
        return self

    def __exit__(self, *_: object) -> None:
        if self._http_client:
            self._http_client.close()
        self._http_client = None
        self._executor = None

    @property
    def flow_token_version(self) -> int:
        return self.tokens.state(FLOW_PROVIDER).version

    def request_head(self) -> RequestHead:
        return RequestHead(
            traceno=self.job.trace_id,
            starttime=_format_start_time(self.job.created_at),
            product=self.job.product,
        )

    def request(
        self,
        step: str,
        endpoint: EndpointSpec[ResponseModel],
        *,
        payload: dict[str, object] | None,
        req_message: dict[str, object],
    ) -> ResponseModel:
        if self._executor is None:
            raise RuntimeError("MockProductClient 必须在 with 块中使用")
        return self._executor.execute(
            endpoint,
            form_data={
                "payload": payload or {},
                "req_message": req_message,
            },
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(self.job, step=step),
        )


def create_product_http_client(fixed_token: str) -> HttpClient:
    if settings.EXTERNAL_SYSTEM_MODE == "mock":
        return create_mock_http_client(fixed_token)
    if not settings.MOCK_PRODUCT_BASE_URL:
        raise ImproperlyConfigured("MOCK_PRODUCT_BASE_URL 未配置")
    return HttpClient(
        HttpClientConfig(
            base_url=settings.MOCK_PRODUCT_BASE_URL,
            timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
            connect_timeout_seconds=settings.HTTP_CONNECT_TIMEOUT_SECONDS,
            write_timeout_seconds=settings.HTTP_WRITE_TIMEOUT_SECONDS,
            pool_timeout_seconds=settings.HTTP_POOL_TIMEOUT_SECONDS,
            max_retries=settings.HTTP_MAX_RETRIES,
            retry_backoff_seconds=settings.HTTP_RETRY_BACKOFF_SECONDS,
            retry_max_backoff_seconds=settings.HTTP_RETRY_MAX_BACKOFF_SECONDS,
        )
    )


def create_mock_http_client(fixed_token: str) -> HttpClient:
    return HttpClient(
        HttpClientConfig(base_url="https://mock-product.local", max_retries=0),
        transport=create_mock_product_transport(fixed_token),
    )


def _format_start_time(value: datetime) -> str:
    return timezone.localtime(value).strftime("%Y%m%d%H%M%S")
