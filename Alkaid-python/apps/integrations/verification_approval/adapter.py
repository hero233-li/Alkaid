from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pydantic import BaseModel

from apps.integrations.auth import TokenManager
from apps.integrations.contracts import EndpointSpec, ResponseModel
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.integrations.verification_approval.api import (
    SEARCH_VERIFICATION_TASK,
    action_endpoint,
    claim_endpoint,
    return_endpoint,
    update_item_endpoint,
)
from apps.integrations.verification_approval.mock_transport import (
    create_verification_approval_mock_transport,
)
from apps.integrations.verification_approval.models import (
    SearchVerificationTaskRequest,
    VerificationActionRequest,
    VerificationItemUpdateRequest,
    VerificationTask,
)


class VerificationApprovalAdapter:
    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self._client: HttpClient | None = None
        self._executor: EndpointExecutor | None = None

    def __enter__(self) -> "VerificationApprovalAdapter":
        self._client = _create_client()
        self._executor = EndpointExecutor(self._client, TokenManager({}))
        return self

    def __exit__(self, *_: object) -> None:
        if self._client:
            self._client.close()
        self._client = None
        self._executor = None

    def search(self, request: SearchVerificationTaskRequest) -> VerificationTask | None:
        return self._execute(SEARCH_VERIFICATION_TASK, request).data

    def claim(self, task_id: str) -> VerificationTask:
        return self._required(self._execute(claim_endpoint(task_id), None).data)

    def return_to_pool(self, task_id: str) -> VerificationTask:
        return self._required(self._execute(return_endpoint(task_id), None).data)

    def update_item(
        self,
        task_id: str,
        item_id: str,
        status: str,
    ) -> VerificationTask:
        response = self._execute(
            update_item_endpoint(task_id, item_id),
            VerificationItemUpdateRequest(status=status),
        )
        return self._required(response.data)

    def apply_action(self, task_id: str, action: str) -> VerificationTask:
        response = self._execute(
            action_endpoint(task_id, action),
            VerificationActionRequest(action=action),
        )
        return self._required(response.data)

    def _execute(
        self,
        endpoint: EndpointSpec[ResponseModel],
        body: BaseModel | None,
    ) -> ResponseModel:
        if self._executor is None:
            raise RuntimeError("VerificationApprovalAdapter 必须在 with 块中使用")
        return self._executor.execute(
            endpoint,
            body=body,
            trace_id=self.trace_id,
        )

    @staticmethod
    def _required(task: VerificationTask | None) -> VerificationTask:
        if task is None:
            raise ValueError("核实任务不存在")
        return task


def _create_client() -> HttpClient:
    if settings.EXTERNAL_SYSTEM_MODE == "mock":
        return HttpClient(
            HttpClientConfig(base_url="https://mock-verification-approval.local", max_retries=0),
            transport=create_verification_approval_mock_transport(),
        )
    if not settings.VERIFICATION_APPROVAL_BASE_URL:
        raise ImproperlyConfigured("VERIFICATION_APPROVAL_BASE_URL 未配置")
    return HttpClient(
        HttpClientConfig(
            base_url=settings.VERIFICATION_APPROVAL_BASE_URL,
            token=settings.VERIFICATION_APPROVAL_API_TOKEN or None,
            timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
            connect_timeout_seconds=settings.HTTP_CONNECT_TIMEOUT_SECONDS,
            write_timeout_seconds=settings.HTTP_WRITE_TIMEOUT_SECONDS,
            pool_timeout_seconds=settings.HTTP_POOL_TIMEOUT_SECONDS,
            max_retries=settings.HTTP_MAX_RETRIES,
            retry_backoff_seconds=settings.HTTP_RETRY_BACKOFF_SECONDS,
            retry_max_backoff_seconds=settings.HTTP_RETRY_MAX_BACKOFF_SECONDS,
        )
    )
