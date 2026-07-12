from apps.integrations.mock_product.api import (
    FIXED_AUDIT,
    LOGIN,
    PRODUCT_CHECKS,
    ROTATE_TOKEN,
    SUBMIT_APPLICATION,
)
from apps.integrations.mock_product.client import MockProductClient
from apps.integrations.mock_product.messages import new_message
from apps.integrations.mock_product.models import (
    OperationResponse,
    ProductCheckInput,
    ProductSubmissionInput,
    RequestHead,
)
from apps.jobs.models import Job


class MockProductApplicationAdapter:
    """Application-domain adapter for the mock product external system."""

    def __init__(self, job: Job) -> None:
        self._client = MockProductClient(job)

    def __enter__(self) -> "MockProductApplicationAdapter":
        self._client.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._client.__exit__(*args)

    @property
    def flow_token_version(self) -> int:
        return self._client.flow_token_version

    def request_head(self) -> RequestHead:
        return self._client.request_head()

    def login(self, head: RequestHead) -> None:
        self._client.request(
            "auth.login",
            LOGIN,
            req_message={
                "req_head": head.model_dump(mode="json"),
                "req_body": {"product": head.product},
            },
            payload={
                "starttime": head.starttime,
                "traceno": head.traceno,
            },
        )

    def check_product(self, head: RequestHead, request: ProductCheckInput) -> OperationResponse:
        try:
            endpoint = PRODUCT_CHECKS[request.product]
        except KeyError:
            raise ValueError(f"未配置产品检查接口：{request.product}") from None
        return self._client.request(
            "product.check",
            endpoint,
            req_message={
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
            payload={
                "bizcond": {"productType": request.product_type},
                "starttime": head.starttime,
                "traceno": head.traceno,
            },
        )

    def rotate_token(self, head: RequestHead) -> None:
        self._client.request(
            "auth.rotate",
            ROTATE_TOKEN,
            req_message={
                "req_head": head.model_dump(mode="json"),
                "req_body": {"reason": "申请阶段切换"},
            },
            payload={
                "traceno": head.traceno,
            },
        )

    def submit_application(
        self,
        head: RequestHead,
        request: ProductSubmissionInput,
    ) -> OperationResponse:
        req_message = new_message("application", "product_apply_v1")
        req_body = req_message["REQ_BODY"]
        body = req_body["request"]
        body["custNme"] = request.customer_name
        body["idtyNo"] = request.certificate_no
        body["orderNo"] = request.order_no or self._default_order_no(head)
        body["organizationCode"] = request.organization_code
        body["outletCode"] = request.outlet_code
        body["phone"] = request.phone
        body["customerType"] = request.customer_type
        body["applicationMethod"] = request.application_method
        body["risk"] = request.risk
        if request.dynamic_term is not None:
            body["dynamicTerm"] = request.dynamic_term
        if request.dynamic_amount is not None:
            body["dynamicAmount"] = request.dynamic_amount
        if request.extra_reason is not None:
            body["extraReason"] = request.extra_reason

        return self._client.request(
            "product.submit",
            SUBMIT_APPLICATION,
            req_message=req_message,
            payload={
                "product": request.product,
                "environment": request.environment,
                "productType": request.product_type,
            },
        )

    def audit(self, head: RequestHead) -> None:
        self._client.request(
            "fixed.audit",
            FIXED_AUDIT,
            req_message={
                "req_head": head.model_dump(mode="json"),
                "req_body": {"jobId": self._client.job.id, "product": head.product},
            },
            payload={
                "traceno": head.traceno,
            },
        )

    @staticmethod
    def _default_order_no(head: RequestHead) -> str:
        return f"{head.starttime[:12]}{head.traceno[:6].upper()}"
