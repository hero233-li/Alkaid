import json
from datetime import datetime
from urllib.parse import parse_qs

import httpx
from django.conf import settings
from django.utils import timezone

from apps.integrations.auth import FlowTokenProvider, StaticTokenProvider, TokenManager
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.integrations.mock_product.api import FIXED_PROVIDER, FLOW_PROVIDER
from apps.integrations.mock_product.models import OperationResponse, RequestHead
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
        self._http_client = create_mock_http_client(self._fixed_token)
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

    def call(self, step: str, endpoint: object, fields: dict[str, object]) -> OperationResponse:
        if self._executor is None:
            raise RuntimeError("MockProductClient 必须在 with 块中使用")
        return self._executor.execute(
            endpoint,  # type: ignore[arg-type]
            form_data=fields,
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(self.job, step=step),
        )


def create_mock_http_client(fixed_token: str) -> HttpClient:
    state = {"flow_token": "flow-token-v1"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = _request_payload(request)
        if path == "/auth/token":
            return httpx.Response(200, json={"data": {"token": state["flow_token"]}})

        if path == "/fixed/audit":
            if request.headers.get("X-Api-Token") != fixed_token:
                return httpx.Response(401, json={"code": "UNAUTHORIZED"})
            return httpx.Response(
                200,
                json={"code": "0000", "message": "固定 Token 校验成功", "data": payload},
            )

        expected = f"Bearer {state['flow_token']}"
        if request.headers.get("Authorization") != expected:
            return httpx.Response(401, json={"code": "UNAUTHORIZED"})
        if path == "/auth/rotate":
            state["flow_token"] = "flow-token-v2"
            return httpx.Response(
                200,
                headers={"X-New-Token": state["flow_token"]},
                json={"code": "0000", "message": "Token 已更新", "data": payload},
            )
        if path.startswith("/checks/"):
            return httpx.Response(
                200,
                json={"code": "0000", "message": "产品检查通过", "data": payload},
            )
        if path.startswith("/applications"):
            return httpx.Response(
                200,
                json={
                    "code": "0000",
                    "message": "产品申请成功",
                    "data": {"applicationNo": "MOCK-APPLICATION-001"},
                },
            )
        return httpx.Response(404, json={"code": "NOT_FOUND"})

    return HttpClient(
        HttpClientConfig(base_url="https://mock-product.local", max_retries=0),
        transport=httpx.MockTransport(handler),
    )


def _request_payload(request: httpx.Request) -> dict[str, object]:
    content = request.content.decode("utf-8") if request.content else ""
    if "application/x-www-form-urlencoded" in request.headers.get("Content-Type", ""):
        parsed = parse_qs(content, keep_blank_values=True)
        result: dict[str, object] = {}
        for name, values in parsed.items():
            value = values[-1]
            try:
                result[name] = json.loads(value)
            except json.JSONDecodeError:
                result[name] = value
        return result
    return json.loads(content or "{}")


def _format_start_time(value: datetime) -> str:
    return timezone.localtime(value).strftime("%Y%m%d%H%M%S")
