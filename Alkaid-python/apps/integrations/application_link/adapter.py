"""External application-link wire contract: one five-field form request."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from apps.integrations.application_link.api import CREATE_DYNAMIC_LINK, CREATE_SUN_CODE_LINK
from apps.integrations.application_link.mock_transport import (
    create_application_link_mock_transport,
)
from apps.integrations.application_link.models import (
    ApplicationLinks,
    GenerateApplicationLinkRequest,
)
from apps.integrations.auth import TokenManager
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


class ApplicationLinkAdapter:
    """Per-Job adapter that records exactly one external call."""

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

    def generate_link(self, request: GenerateApplicationLinkRequest) -> ApplicationLinks:
        if request.category == "动态链接":
            endpoint = CREATE_DYNAMIC_LINK
        elif request.category == "太阳码":
            endpoint = CREATE_SUN_CODE_LINK
        else:
            raise ValueError(f"未知申请链接类别：{request.category}")
        message = _serialize_message(
            {
                "REQ_HEAD": {
                    "traceno": self.job.trace_id,
                    "starttime": self.job.created_at.isoformat(),
                    "product": request.product,
                },
                "REQ_BODY": {"request": request.external_request()},
            }
        )
        response = self._execute(
            "application_link.generate_link",
            endpoint,
            form_data={
                "msg_id": self.job.trace_id,
                "sign": _configured_sign(message),
                "timestamp": datetime.now(timezone.utc).strftime(
                    settings.APPLICATION_LINK_TIMESTAMP_FORMAT
                ),
                "REQ_MESSAGE": message,
                "biz_content": message,
            },
        )
        return response.data

    def _execute(self, step: str, endpoint: object, *, form_data: dict[str, str]):
        if self._executor is None:
            raise RuntimeError("ApplicationLinkAdapter 必须在 with 块中使用")
        return self._executor.execute(
            endpoint,  # type: ignore[arg-type]
            form_data=form_data,
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(self.job, step=step),
        )


def _serialize_message(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _configured_sign(message: str) -> str:
    """Resolve the configured signer without inventing an unconfirmed algorithm."""
    if settings.EXTERNAL_SYSTEM_MODE == "real":
        if not settings.APPLICATION_LINK_SIGNER:
            raise ImproperlyConfigured("APPLICATION_LINK_SIGNER 未配置")
        signer = import_string(settings.APPLICATION_LINK_SIGNER)
        sign = signer(message)
        if not isinstance(sign, str) or not sign:
            raise ImproperlyConfigured("APPLICATION_LINK_SIGNER 必须返回非空字符串")
        return sign
    sign = settings.APPLICATION_LINK_FORM_SIGN
    if settings.APPLICATION_LINK_SIGN_REQUIRED and not sign:
        raise ImproperlyConfigured("APPLICATION_LINK_FORM_SIGN 未配置")
    return sign


def _create_client() -> HttpClient:
    if settings.EXTERNAL_SYSTEM_MODE == "mock":
        return _create_mock_client()
    if not settings.APPLICATION_LINK_PROTOCOL_CONFIRMED:
        raise ImproperlyConfigured(
            "申请链接真实协议尚未确认；请完成签名、时间戳、路径和响应字段联调后设置 "
            "APPLICATION_LINK_PROTOCOL_CONFIRMED=true"
        )
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
