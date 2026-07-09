from dataclasses import dataclass
from typing import ClassVar

from django.conf import settings
from django.utils import timezone

from apps.integrations.auth import FlowTokenProvider, StaticTokenProvider, TokenManager
from apps.integrations.executor import EndpointExecutor
from apps.integrations.mock_product.api import (
    FIXED_AUDIT,
    FIXED_PROVIDER,
    FLOW_PROVIDER,
    LOGIN,
    ROTATE_TOKEN,
    SUBMIT_APPLICATION,
    create_mock_http_client,
)
from apps.integrations.mock_product.models import OperationResponse
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job
from apps.product_data.schemas import ProductApplicationSubmission


@dataclass
class ProductHandlerContext:
    job: Job
    submission: ProductApplicationSubmission
    executor: EndpointExecutor
    tokens: TokenManager

    @property
    def trace_no(self) -> str:
        return self.job.trace_id

    @property
    def start_time(self) -> str:
        return timezone.localtime(self.job.created_at).strftime("%Y%m%d%H%M%S")

    def request_head(self) -> dict[str, object]:
        return {
            "traceno": self.trace_no,
            "starttime": self.start_time,
            "product": self.submission.product,
        }

    def call(self, step: str, endpoint, fields: dict[str, object]):
        return self.executor.execute(
            endpoint,
            form_data=fields,
            trace_id=self.job.trace_id,
            observer=JobHttpCallObserver(self.job, step=step),
        )


class BaseProductApplicationHandler:
    code: ClassVar[str]
    product_type: ClassVar[str]
    switch_name: ClassVar[str]
    check_endpoint: ClassVar[object]

    def execute(
        self,
        job: Job,
        submission: ProductApplicationSubmission,
    ) -> dict[str, object]:
        fixed_token = settings.MOCK_FIXED_SYSTEM_TOKEN
        tokens = TokenManager(
            {
                FLOW_PROVIDER: FlowTokenProvider(),
                FIXED_PROVIDER: StaticTokenProvider(fixed_token),
            }
        )
        with create_mock_http_client(fixed_token) as client:
            context = ProductHandlerContext(
                job=job,
                submission=submission,
                executor=EndpointExecutor(client, tokens),
                tokens=tokens,
            )
            self.login(context)
            version_after_login = tokens.state(FLOW_PROVIDER).version
            self.check_product(context)
            version_after_check = tokens.state(FLOW_PROVIDER).version
            self.rotate_token(context)
            version_after_rotate = tokens.state(FLOW_PROVIDER).version
            application = self.submit_application(context)
            version_after_submit = tokens.state(FLOW_PROVIDER).version
            self.audit(context)

        return {
            "applicationNo": application.data["applicationNo"],
            "flowTokenVersions": {
                "login": version_after_login,
                "check": version_after_check,
                "rotate": version_after_rotate,
                "submit": version_after_submit,
            },
            "fixedTokenCall": "success",
            "handler": self.code,
        }

    def login(self, ctx: ProductHandlerContext) -> None:
        ctx.call(
            "auth.login",
            LOGIN,
            {
                "req_message": {
                    "req_head": ctx.request_head(),
                    "req_body": {"product": ctx.submission.product},
                },
                "starttime": ctx.start_time,
                "traceno": ctx.trace_no,
            },
        )

    def check_product(self, ctx: ProductHandlerContext) -> OperationResponse:
        return ctx.call(
            "product.check",
            self.check_endpoint,
            {
                "req_message": {
                    "req_head": ctx.request_head(),
                    "req_body": {
                        "request": {
                            "product": ctx.submission.product,
                            "customerType": ctx.submission.payload["customerType"],
                            "switchName": self.switch_name,
                            "switchEnabled": bool(
                                ctx.submission.payload[self.switch_name]
                            ),
                        }
                    },
                },
                "bizcond": {"productType": self.product_type},
                "starttime": ctx.start_time,
                "traceno": ctx.trace_no,
            },
        )

    def rotate_token(self, ctx: ProductHandlerContext) -> None:
        ctx.call(
            "auth.rotate",
            ROTATE_TOKEN,
            {
                "req_message": {
                    "req_head": ctx.request_head(),
                    "req_body": {"reason": "申请阶段切换"},
                },
                "traceno": ctx.trace_no,
            },
        )

    def submit_application(self, ctx: ProductHandlerContext) -> OperationResponse:
        payload = {
            "customer": {
                "name": ctx.submission.payload["personName"],
                "certificateNo": ctx.submission.payload["certificateNo"],
                "phone": ctx.submission.payload["phone"],
                "type": ctx.submission.payload["customerType"],
            },
            "application": {
                "organizationCode": ctx.submission.payload["branch"],
                "outletCode": ctx.submission.payload["outlet"],
                "method": ctx.submission.payload["applicationMethod"],
            },
            "risk": {
                name: ctx.submission.payload[name]
                for name in (
                    "whitelistEnabled",
                    "redShieldEnabled",
                    "creditEnabled",
                )
                if name in ctx.submission.payload
            },
        }
        for source, target in (
            ("dynamicTerm", "term"),
            ("dynamicAmount", "amount"),
            ("extraReason", "extraReason"),
        ):
            if source in ctx.submission.payload:
                payload["application"][target] = ctx.submission.payload[source]

        return ctx.call(
            "product.submit",
            SUBMIT_APPLICATION,
            {
                "req_message": {
                    "req_head": ctx.request_head(),
                    "req_body": {"request": payload},
                },
                "bizcond": {
                    "productType": self.product_type,
                    "organizationCode": ctx.submission.payload["branch"],
                },
                "starttime": ctx.start_time,
                "traceno": ctx.trace_no,
            },
        )

    def audit(self, ctx: ProductHandlerContext) -> None:
        ctx.call(
            "fixed.audit",
            FIXED_AUDIT,
            {
                "req_message": {
                    "req_head": ctx.request_head(),
                    "req_body": {
                        "jobId": ctx.job.id,
                        "product": ctx.submission.product,
                    },
                },
                "traceno": ctx.trace_no,
            },
        )
