from typing import ClassVar

from apps.integrations.mock_product.adapter import MockProductAdapter
from apps.integrations.mock_product.models import ProductCheckInput, ProductSubmissionInput
from apps.jobs.models import Job
from apps.product_data.product_applications.schemas import ProductApplicationSubmission


class BaseProductApplicationHandler:
    """Orchestrates the product flow; integration owns every wire-format detail."""

    code: ClassVar[str]
    product_type: ClassVar[str]
    switch_name: ClassVar[str]
    check_code: ClassVar[str]

    def execute(self, job: Job, submission: ProductApplicationSubmission) -> dict[str, object]:
        with MockProductAdapter(job) as adapter:
            request_head = adapter.request_head()
            adapter.login(request_head)
            version_after_login = adapter.flow_token_version
            adapter.check_product(
                request_head,
                ProductCheckInput(
                    product=self.check_code,
                    customer_type=submission.payload["customerType"],
                    switch_name=self.switch_name,
                    switch_enabled=bool(submission.payload[self.switch_name]),
                    product_type=self.product_type,
                ),
            )
            version_after_check = adapter.flow_token_version
            adapter.rotate_token(request_head)
            version_after_rotate = adapter.flow_token_version
            application = adapter.submit_application(
                request_head,
                ProductSubmissionInput(
                    product_type=self.product_type,
                    organization_code=submission.payload["branch"],
                    customer_name=submission.payload["personName"],
                    certificate_no=submission.payload["certificateNo"],
                    phone=submission.payload["phone"],
                    customer_type=submission.payload["customerType"],
                    outlet_code=submission.payload["outlet"],
                    application_method=submission.payload["applicationMethod"],
                    risk={
                        name: submission.payload[name]
                        for name in ("whitelistEnabled", "redShieldEnabled", "creditEnabled")
                        if name in submission.payload
                    },
                    dynamic_term=submission.payload.get("dynamicTerm"),
                    dynamic_amount=submission.payload.get("dynamicAmount"),
                    extra_reason=submission.payload.get("extraReason"),
                ),
            )
            version_after_submit = adapter.flow_token_version
            adapter.audit(request_head)

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
