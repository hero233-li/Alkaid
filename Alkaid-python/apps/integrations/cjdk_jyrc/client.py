import json
import logging
import uuid
from typing import Any
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.utils import timezone

from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.mock_transport import create_mock_transport
from apps.integrations.contracts import EndpointSpec, ResponseModel, RetryMode
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.jobs.http import (
    JobHttpCallObserver,
    format_log_value,
    sanitize_url,
)
from apps.jobs.models import Job
from apps.jobs.services import add_job_log

logger = logging.getLogger(__name__)

SESSION_RESPONSE_HEADERS = ("X-Token", "X-FCOS-SESSIONID", "X-Sd")


class CjdkJyrcClient:
    """One environment-bound HTTP session shared by page and agreement steps."""

    def __init__(self, job: Job, environment: str) -> None:
        self.job = job
        self.environment = environment
        self.base_url = config.resolve_base_url(environment)
        self._http_client: HttpClient | None = None
        self._session_headers: dict[str, str] = {}
        self._session_established = False
        self._session_final_url: str | None = None

    def __enter__(self) -> "CjdkJyrcClient":
        transport = (
            create_mock_transport()
            if config.external_system_mode() == "mock"
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
                follow_redirects=True,
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
    def session_cookie_names(self) -> tuple[str, ...]:
        if self._http_client is None:
            return ()
        return self._http_client.cookie_names

    @property
    def session_header_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._session_headers))

    @property
    def session_final_url(self) -> str | None:
        return self._session_final_url

    def acquire_session(self, application_url: str) -> None:
        if self._http_client is None:
            raise RuntimeError("CjdkJyrcClient 必须在 with 块中使用")
        parsed = urlsplit(application_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("申请链接必须是有效的 HTTP/HTTPS URL")
        if parsed.username or parsed.password:
            raise ValueError("申请链接不能包含 URL 用户名或密码")

        auth_values = parse_qs(
            parsed.query,
            keep_blank_values=True,
        ).get("auth", [])
        self._write_diagnostic(
            "Session 初始化入口",
            {
                "currentImplementation": (
                    "GET application URL and follow redirects"
                ),
                "applicationUrl": sanitize_url(application_url),
                "authParameterPresent": bool(auth_values),
                "authParameterLength": (
                    len(auth_values[0])
                    if auth_values
                    else 0
                ),
                "environment": self.environment,
            },
        )

        response = self._http_client.open_url(
            "GET",
            application_url,
            headers={"Accept": "text/html,application/xhtml+xml"},
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(
                self.job,
                step="application_link.acquire_session",
            ),
        )
        chain = [*response.history, response]
        for item in chain:
            self._capture_session(dict(item.headers))

        self._session_final_url = str(response.url)
        if self.session_cookie_names:
            self._session_established = True

        self._write_diagnostic(
            "Session 当前获取结果",
            {
                "redirectChain": [
                    {
                        "statusCode": item.status_code,
                        "url": sanitize_url(str(item.url)),
                        "setCookiePresent": (
                            "set-cookie"
                            in {
                                name.lower()
                                for name in item.headers
                            }
                        ),
                        "sessionResponseHeaders": [
                            header_name
                            for header_name in SESSION_RESPONSE_HEADERS
                            if item.headers.get(header_name)
                        ],
                    }
                    for item in chain
                ],
                "finalUrl": sanitize_url(str(response.url)),
                "cookieNames": list(self.session_cookie_names),
                "forwardedHeaderNames": list(self.session_header_names),
                "sessionEstablishedByCurrentCheck": self._session_established,
                "warning": (
                    "当前仍只验证 Cookie/会话头是否存在；"
                    "尚未实现 auth 换取客户端 TokenId 的专用初始化步骤"
                ),
            },
            level="INFO" if self._session_established else "ERROR",
        )

        if not self._session_established:
            raise RuntimeError(
                "调用申请链接成功，但没有建立可复用的外系统 Session；"
                "请检查 Session 当前获取结果日志"
            )

    def request(
        self,
        *,
        step: str,
        endpoint: EndpointSpec[ResponseModel],
        message: dict[str, Any],
    ) -> ResponseModel:
        if self._http_client is None:
            raise RuntimeError("CjdkJyrcClient 必须在 with 块中使用")
        if not self._session_established:
            raise RuntimeError("尚未调用申请链接建立 Session，不能请求协议接口")

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
        if self.session_cookie_names:
            self._session_established = True
        return result.data

    def _write_diagnostic(
        self,
        title: str,
        content: dict[str, Any],
        *,
        level: str = "INFO",
    ) -> None:
        message = (
            f"{title}（敏感值已脱敏）：\n"
            f"{format_log_value(content)}"
        )
        add_job_log(
            self.job,
            level,
            message,
            step="application_link.acquire_session",
            celery_task_id=self.job.celery_task_id,
            metadata={
                "event": "session_diagnostic",
                "title": title,
            },
        )
        log_method = logger.error if level == "ERROR" else logger.info
        log_method(
            "session_diagnostic %s\n%s",
            title,
            format_log_value(content),
        )

    def _capture_session(self, response_headers: dict[str, str]) -> None:
        normalized = {name.lower(): value for name, value in response_headers.items()}
        if "set-cookie" in normalized:
            self._session_established = True
        for header_name in SESSION_RESPONSE_HEADERS:
            value = normalized.get(header_name.lower())
            if value:
                self._session_headers[header_name] = value
                self._session_established = True
