"""Application-link integration used only by the product-application flow."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from apps.integrations.auth import TokenManager
from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.api import (
    CREATE_DYNAMIC_LINK,
    CREATE_SUN_CODE_LINK,
)
from apps.integrations.cjdk_jyrc.mock_transport import create_mock_transport
from apps.integrations.cjdk_jyrc.models import ApplicationLinks
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


class CjdkJyrcApplicationLinkAdapter:
    """Generate one application link before the product-page session is opened."""

    def __init__(self, job: Job, environment: str) -> None:
        self.job = job
        self.environment = environment
        self._client: HttpClient | None = None
        self._executor: EndpointExecutor | None = None

    def __enter__(self) -> "CjdkJyrcApplicationLinkAdapter":
        self._client = self._create_client()
        self._executor = EndpointExecutor(self._client, TokenManager({}))
        return self

    def __exit__(self, *_: object) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._executor = None

    def generate_link(
        self,
        *,
        product: str,
        category: str,
        payload: dict[str, Any],
    ) -> ApplicationLinks:
        if category == "动态链接":
            endpoint = CREATE_DYNAMIC_LINK
        elif category == "太阳码":
            endpoint = CREATE_SUN_CODE_LINK
        else:
            raise ValueError(f"未知申请链接类别：{category}")

        project_id = payload.get("projectId") or payload.get("cooperationProjectId")
        external_request: dict[str, Any] = {
            "env": self.environment,
            "product": product,
            "category": category,
            "payload": payload,
        }
        if project_id:
            external_request["cooperationProjectId"] = str(project_id)

        message = json.dumps(
            {
                "REQ_HEAD": {
                    "traceno": self.job.trace_id,
                    "starttime": self.job.created_at.isoformat(),
                    "product": product,
                },
                "REQ_BODY": {"request": external_request},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        response = self._execute(
            endpoint=endpoint,
            form_data={
                "msg_id": self.job.trace_id,
                "sign": self._configured_sign(message),
                "timestamp": datetime.now(timezone.utc).strftime(
                    settings.APPLICATION_LINK_TIMESTAMP_FORMAT
                ),
                "REQ_MESSAGE": message,
                "biz_content": message,
            },
        )
        return response.data

    def _execute(self, *, endpoint: object, form_data: dict[str, str]):
        if self._executor is None:
            raise RuntimeError("CjdkJyrcApplicationLinkAdapter 必须在 with 块中使用")
        return self._executor.execute(
            endpoint,  # type: ignore[arg-type]
            form_data=form_data,
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(
                self.job,
                step="application_link.generate_link",
            ),
        )

    def _configured_sign(self, message: str) -> str:
        if settings.EXTERNAL_SYSTEM_MODE == "real":
            if not settings.APPLICATION_LINK_PROTOCOL_CONFIRMED:
                raise ImproperlyConfigured(
                    "申请链接真实协议尚未确认；请确认路径、签名和响应字段后设置 "
                    "APPLICATION_LINK_PROTOCOL_CONFIRMED=true"
                )
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

    def _create_client(self) -> HttpClient:
        transport = create_mock_transport() if settings.EXTERNAL_SYSTEM_MODE == "mock" else None
        return HttpClient(
            HttpClientConfig(
                base_url=config.resolve_application_link_base_url(self.environment),
                token=settings.APPLICATION_LINK_API_TOKEN or None,
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
