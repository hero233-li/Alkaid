"""Typed boundary for the mock product system.

The product-application domain only supplies semantic input values.  This
module owns the external system's form-envelope layout, endpoints and tokens.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.conf import settings

from apps.integrations.auth import FlowTokenProvider, StaticTokenProvider, TokenManager
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import HttpClient
from apps.integrations.mock_product.api import (
    FIXED_AUDIT,
    FIXED_PROVIDER,
    FLOW_PROVIDER,
    LOGIN,
    PRODUCT_CHECKS,
    ROTATE_TOKEN,
    SUBMIT_APPLICATION,
    create_mock_http_client,
)
from apps.integrations.mock_product.models import (
    OperationResponse,
    ProductCheckInput,
    ProductSubmissionInput,
    RequestHead,
)
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


class MockProductAdapter:
    """Per-Job adapter; flow tokens are never shared between task attempts."""

    def __init__(self, job: Job) -> None:
        self.job = job
        self._fixed_token = settings.MOCK_FIXED_SYSTEM_TOKEN
        self.tokens = TokenManager(
            {
                FLOW_PROVIDER: FlowTokenProvider(),
                FIXED_PROVIDER: StaticTokenProvider(self._fixed_token),
            }
        )
        self._client: HttpClient | None = None
        self._executor: EndpointExecutor | None = None

    def __enter__(self) -> MockProductAdapter:
        self._client = create_mock_http_client(self._fixed_token)
        self._executor = EndpointExecutor(self._client, self.tokens)
        return self

    def __exit__(self, *_: object) -> None:
        if self._client:
            self._client.close()
        self._client = None
        self._executor = None

    @property
    def flow_token_version(self) -> int:
        return self.tokens.state(FLOW_PROVIDER).version

    def login(self, head: RequestHead) -> None:
        self._call(
            "auth.login",
            LOGIN,
            {
                "req_message": {
                    "req_head": head.model_dump(mode="json"),
                    "req_body": {"product": head.product},
                },
                "starttime": head.starttime,
                "traceno": head.traceno,
            },
        )

    def check_product(self, head: RequestHead, request: ProductCheckInput) -> OperationResponse:
        try:
            endpoint = PRODUCT_CHECKS[request.product]
        except KeyError:
            raise ValueError(f"未配置产品检查接口：{request.product}") from None
        return self._call(
            "product.check",
            endpoint,
            {
                "req_message": {
                    "req_head": head.model_dump(mode="json"),
                    "req_body": {
                        "request": {
                            "product": request.product,
                            "customerType": request.customer_type,
                            "switchName": request.switch_name,
                            "switchEnabled": request.switch_enabled,
                        }
                    },
                },
                "bizcond": {"productType": request.product_type},
                "starttime": head.starttime,
                "traceno": head.traceno,
            },
        )

    def rotate_token(self, head: RequestHead) -> None:
        self._call(
            "auth.rotate",
            ROTATE_TOKEN,
            {
                "req_message": {
                    "req_head": head.model_dump(mode="json"),
                    "req_body": {"reason": "申请阶段切换"},
                },
                "traceno": head.traceno,
            },
        )

    def submit_application(
        self,
        head: RequestHead,
        request: ProductSubmissionInput,
    ) -> OperationResponse:
        application: dict[str, Any] = {
            "organizationCode": request.organization_code,
            "outletCode": request.outlet_code,
            "method": request.application_method,
        }
        if request.dynamic_term is not None:
            application["term"] = request.dynamic_term
        if request.dynamic_amount is not None:
            application["amount"] = request.dynamic_amount
        if request.extra_reason is not None:
            application["extraReason"] = request.extra_reason
        return self._call(
            "product.submit",
            SUBMIT_APPLICATION,
            {
                "req_message": {
                    "req_head": head.model_dump(mode="json"),
                    "req_body": {
                        "request": {
                            "customer": {
                                "name": request.customer_name,
                                "certificateNo": request.certificate_no,
                                "phone": request.phone,
                                "type": request.customer_type,
                            },
                            "application": application,
                            "risk": request.risk,
                        }
                    },
                },
                "bizcond": {
                    "productType": request.product_type,
                    "organizationCode": request.organization_code,
                },
                "starttime": head.starttime,
                "traceno": head.traceno,
            },
        )

    def audit(self, head: RequestHead) -> None:
        self._call(
            "fixed.audit",
            FIXED_AUDIT,
            {
                "req_message": {
                    "req_head": head.model_dump(mode="json"),
                    "req_body": {"jobId": self.job.id, "product": head.product},
                },
                "traceno": head.traceno,
            },
        )

    def request_head(self) -> RequestHead:
        return RequestHead(
            traceno=self.job.trace_id,
            starttime=_format_start_time(self.job.created_at),
            product=self.job.product,
        )

    def _call(self, step: str, endpoint: object, fields: dict[str, object]) -> OperationResponse:
        if self._executor is None:
            raise RuntimeError("MockProductAdapter 必须在 with 块中使用")
        return self._executor.execute(
            endpoint,  # type: ignore[arg-type]
            form_data=fields,
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(self.job, step=step),
        )


def _format_start_time(value: datetime) -> str:
    from django.utils import timezone

    return timezone.localtime(value).strftime("%Y%m%d%H%M%S")
