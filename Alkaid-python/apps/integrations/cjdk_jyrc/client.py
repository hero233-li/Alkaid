import json
import uuid
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.mock_transport import create_mock_transport
from apps.integrations.contracts import EndpointSpec, ResponseModel, RetryMode
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


SESSION_RESPONSE_HEADERS = ("X-Token", "X-FCOS-SESSIONID", "X-Sd")


class CjdkJyrcClient:
    """One environment-bound HTTP session shared by all agreement steps."""

    def __init__(self, job: Job, environment: str) -> None:
        self.job = job
        self.environment = environment
        self.base_url = config.resolve_base_url(environment)
        self._http_client: HttpClient | None = None
        self._session_headers: dict[str, str] = {}
        self._session_established = False

    def __enter__(self) -> "CjdkJyrcClient":
        transport = (
            create_mock_transport()
            if settings.EXTERNAL_SYSTEM_MODE == "mock"
            else None
        )
        self._http_client = HttpClient(
            HttpClientConfig(
                base_url=self.base_url,
                timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
                connect_timeout_seconds=settings.HTTP_CONNECT_TIMEOUT_SECONDS,
                write_timeout_seconds=settings.HTTP_WRITE_TIMEOUT_SECONDS,
                pool_timeout_seconds=settings.HTTP_POOL_TIMEOUT_SECONDS,
                max_retries=settings.HTTP_MAX_RETRIES,
                retry_backoff_seconds=settings.HTTP_RETRY_BACKOFF_SECONDS,
                retry_max_backoff_seconds=settings.HTTP_RETRY_MAX_BACKOFF_SECONDS,
            ),
            transport=transport,
        )
        return self

    def __exit__(self, *_: object) -> None:
        if self._http_client is not None:
            self._http_client.close()
        self._http_client = None

    @property
    def session_established(self) -> bool:
        return self._session_established

    @property
    def session_header_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._session_headers))

    def request(
        self,
        *,
        step: str,
        endpoint: EndpointSpec[ResponseModel],
        message: dict[str, Any],
    ) -> ResponseModel:
        if self._http_client is None:
            raise RuntimeError("CjdkJyrcClient 必须在 with 块中使用")

        serialized_message = json.dumps(
            message,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        result = self._http_client.request_detailed(
            endpoint.method,
            endpoint.path,
            response_model=endpoint.response_model,
            form_data={
                "msg_id": str(uuid.uuid4()),
                "sign": config.form_sign(),
                "timestamp": timezone.localtime().strftime(config.timestamp_format()),
                "REQ_MESSAGE": serialized_message,
                "biz_content": serialized_message,
            },
            headers={
                "Accept": "text/javascript;charset=utf-8",
                **self._session_headers,
            },
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(self.job, step=step),
            max_retries=(
                self._http_client.config.max_retries
                if endpoint.retry_mode == RetryMode.SAFE
                else 0
            ),
        )
        self._capture_session(result.headers)
        return result.data

    def _capture_session(self, response_headers: dict[str, str]) -> None:
        normalized = {name.lower(): value for name, value in response_headers.items()}
        if "set-cookie" in normalized:
            self._session_established = True
        for header_name in SESSION_RESPONSE_HEADERS:
            value = normalized.get(header_name.lower())
            if value:
                self._session_headers[header_name] = value
                self._session_established = True
