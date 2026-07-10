from apps.integrations.mock_product.api import (
    FIXED_AUDIT,
    LOGIN,
    PRODUCT_CHECKS,
    ROTATE_TOKEN,
    SUBMIT_APPLICATION,
)
from apps.integrations.mock_product.builders import build_product_apply_form
from apps.integrations.mock_product.client import MockProductClient
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
        self._client.call(
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
        return self._client.call(
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
        self._client.call(
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
        return self._client.call(
            "product.submit",
            SUBMIT_APPLICATION,
            build_product_apply_form(head, request),
        )

    def audit(self, head: RequestHead) -> None:
        self._client.call(
            "fixed.audit",
            FIXED_AUDIT,
            {
                "req_message": {
                    "req_head": head.model_dump(mode="json"),
                    "req_body": {"jobId": self._client.job.id, "product": head.product},
                },
                "traceno": head.traceno,
            },
        )
