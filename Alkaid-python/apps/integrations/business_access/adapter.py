from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pydantic import BaseModel

from apps.integrations.auth import TokenManager
from apps.integrations.business_access.api import (
    SEARCH_BUSINESS_ACCESS,
    invalidate_endpoint,
    push_notification_endpoint,
    query_notifications_endpoint,
)
from apps.integrations.business_access.mock_transport import (
    create_business_access_mock_transport,
)
from apps.integrations.business_access.models import (
    BusinessAccessNotification,
    BusinessAccessRecord,
    NotificationPushResult,
    PushNotificationRequest,
    RecordOperationRequest,
    SearchBusinessAccessRequest,
)
from apps.integrations.contracts import EndpointSpec, ResponseModel
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


class BusinessAccessAdapter:
    def __init__(self, job: Job) -> None:
        self.job = job
        self._client: HttpClient | None = None
        self._executor: EndpointExecutor | None = None

    def __enter__(self) -> "BusinessAccessAdapter":
        self._client = _create_client()
        self._executor = EndpointExecutor(self._client, TokenManager({}))
        return self

    def __exit__(self, *_: object) -> None:
        if self._client:
            self._client.close()
        self._client = None
        self._executor = None

    def search(self, request: SearchBusinessAccessRequest) -> tuple[BusinessAccessRecord, ...]:
        response = self._execute("business_access.search", SEARCH_BUSINESS_ACCESS, request)
        return response.data.records

    def invalidate(self, record_id: int) -> BusinessAccessRecord:
        response = self._execute(
            "business_access.invalidate",
            invalidate_endpoint(record_id),
            RecordOperationRequest(record_id=record_id),
        )
        return response.data.record

    def query_notifications(self, record_id: int) -> tuple[BusinessAccessNotification, ...]:
        response = self._execute(
            "business_access.notifications.query",
            query_notifications_endpoint(record_id),
            RecordOperationRequest(record_id=record_id),
        )
        return response.data.notifications

    def push_notification(
        self,
        record_id: int,
        notification_id: int,
        version_type: str,
    ) -> NotificationPushResult:
        response = self._execute(
            "business_access.notifications.push",
            push_notification_endpoint(record_id, notification_id),
            PushNotificationRequest(
                record_id=record_id,
                notification_id=notification_id,
                version_type=version_type,
            ),
        )
        return response.data.push_result

    def _execute(
        self,
        step: str,
        endpoint: EndpointSpec[ResponseModel],
        body: BaseModel,
    ) -> ResponseModel:
        if self._executor is None:
            raise RuntimeError("BusinessAccessAdapter 必须在 with 块中使用")
        return self._executor.execute(
            endpoint,
            body=body,
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(self.job, step=step),
        )


def _create_client() -> HttpClient:
    if settings.EXTERNAL_SYSTEM_MODE == "mock":
        return HttpClient(
            HttpClientConfig(base_url="https://mock-business-access.local", max_retries=0),
            transport=create_business_access_mock_transport(),
        )
    if not settings.BUSINESS_ACCESS_BASE_URL:
        raise ImproperlyConfigured("BUSINESS_ACCESS_BASE_URL 未配置")
    return HttpClient(
        HttpClientConfig(
            base_url=settings.BUSINESS_ACCESS_BASE_URL,
            token=settings.BUSINESS_ACCESS_API_TOKEN or None,
            timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
            connect_timeout_seconds=settings.HTTP_CONNECT_TIMEOUT_SECONDS,
            write_timeout_seconds=settings.HTTP_WRITE_TIMEOUT_SECONDS,
            pool_timeout_seconds=settings.HTTP_POOL_TIMEOUT_SECONDS,
            max_retries=settings.HTTP_MAX_RETRIES,
            retry_backoff_seconds=settings.HTTP_RETRY_BACKOFF_SECONDS,
            retry_max_backoff_seconds=settings.HTTP_RETRY_MAX_BACKOFF_SECONDS,
        )
    )
