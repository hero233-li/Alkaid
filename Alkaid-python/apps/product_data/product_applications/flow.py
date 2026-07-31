from collections.abc import Callable
from typing import Any

from apps.integrations.mock_product.adapters import MockProductApplicationAdapter
from apps.integrations.mock_product.models import ProductCheckInput, ProductSubmissionInput
from apps.jobs.models import Job
from apps.product_data.catalog import ProductExecutionSnapshot
from apps.product_data.product_applications.context import ProductApplicationContext
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.services import (
    build_product_application_result,
    resolve_product_snapshot,
    validate_submission,
)

ProgressReporter = Callable[..., None]


class ProductApplicationFlow:
    """Execute the current product-application flow in explicit Python order."""

    def execute(
        self,
        *,
        job: Job,
        submission: ProductApplicationSubmission | None = None,
        snapshot: ProductExecutionSnapshot | None = None,
        progress: ProgressReporter | None = None,
    ) -> dict[str, Any]:
        context = self.create_context(
            job=job,
            submission=submission,
            snapshot=snapshot,
        )

        self.parse_submission(context)
        self.load_execution_snapshot(context)
        self.validate_submission(context)
        self.report_validation_completed(progress)

        with MockProductApplicationAdapter(job) as adapter:
            self.create_request_head(context, adapter)
            self.login(context, adapter)
            self.check_product(context, adapter)
            self.rotate_token(context, adapter)
            self.submit_application(context, adapter)
            self.audit(context, adapter)

        self.build_result(context)
        self.report_execution_completed(progress)
        return self.result(context)

    @staticmethod
    def create_context(
        *,
        job: Job,
        submission: ProductApplicationSubmission | None,
        snapshot: ProductExecutionSnapshot | None,
    ) -> ProductApplicationContext:
        return ProductApplicationContext(
            job=job,
            submission=submission,
            execution_snapshot=snapshot,
        )

    @staticmethod
    def parse_submission(context: ProductApplicationContext) -> None:
        if context.submission is None:
            context.submission = ProductApplicationSubmission(
                name=context.job.name,
                product=context.job.product,
                payload=context.job.payload,
            )

    @staticmethod
    def load_execution_snapshot(context: ProductApplicationContext) -> None:
        if context.execution_snapshot is None:
            context.execution_snapshot = resolve_product_snapshot(
                context.job,
                context.job.product,
            )

    @staticmethod
    def validate_submission(context: ProductApplicationContext) -> None:
        validate_submission(
            ProductApplicationFlow._submission(context),
            execution_snapshot=ProductApplicationFlow._snapshot(context),
        )

    @staticmethod
    def report_validation_completed(progress: ProgressReporter | None) -> None:
        if progress is not None:
            progress(stage="validate", progress=40, message="产品申请参数校验完成")

    @staticmethod
    def create_request_head(
        context: ProductApplicationContext,
        adapter: MockProductApplicationAdapter,
    ) -> None:
        context.request_head = adapter.request_head()

    @staticmethod
    def login(
        context: ProductApplicationContext,
        adapter: MockProductApplicationAdapter,
    ) -> None:
        adapter.login(ProductApplicationFlow._request_head(context))
        context.flow_token_versions["login"] = adapter.flow_token_version

    @staticmethod
    def check_product(
        context: ProductApplicationContext,
        adapter: MockProductApplicationAdapter,
    ) -> None:
        submission = ProductApplicationFlow._submission(context)
        snapshot = ProductApplicationFlow._snapshot(context)
        adapter.check_product(
            ProductApplicationFlow._request_head(context),
            ProductCheckInput(
                product=snapshot.product_code,
                customer_type=submission.payload["customerType"],
                switch_name=snapshot.switch_field,
                switch_enabled=bool(submission.payload[snapshot.switch_field]),
                product_type=snapshot.product_type,
            ),
        )
        context.flow_token_versions["check"] = adapter.flow_token_version

    @staticmethod
    def rotate_token(
        context: ProductApplicationContext,
        adapter: MockProductApplicationAdapter,
    ) -> None:
        adapter.rotate_token(ProductApplicationFlow._request_head(context))
        context.flow_token_versions["rotate"] = adapter.flow_token_version

    @staticmethod
    def submit_application(
        context: ProductApplicationContext,
        adapter: MockProductApplicationAdapter,
    ) -> None:
        submission = ProductApplicationFlow._submission(context)
        snapshot = ProductApplicationFlow._snapshot(context)
        context.application_response = adapter.submit_application(
            ProductApplicationFlow._request_head(context),
            ProductSubmissionInput(
                product=submission.product,
                environment=submission.payload["environment"],
                product_type=snapshot.product_type,
                organization_code=submission.payload["branch"],
                customer_name=submission.payload["personName"],
                certificate_no=submission.payload["certificateNo"],
                phone=submission.payload["phone"],
                customer_type=submission.payload["customerType"],
                outlet_code=submission.payload["outlet"],
                application_method=submission.payload["applicationMethod"],
                risk={
                    name: submission.payload[name]
                    for name in (
                        "whitelistEnabled",
                        "redShieldEnabled",
                        "creditEnabled",
                    )
                    if name in submission.payload
                },
                dynamic_term=submission.payload.get("dynamicTerm"),
                dynamic_amount=submission.payload.get("dynamicAmount"),
                extra_reason=submission.payload.get("extraReason"),
            ),
        )
        context.flow_token_versions["submit"] = adapter.flow_token_version

    @staticmethod
    def audit(
        context: ProductApplicationContext,
        adapter: MockProductApplicationAdapter,
    ) -> None:
        adapter.audit(ProductApplicationFlow._request_head(context))

    @staticmethod
    def build_result(context: ProductApplicationContext) -> None:
        application = ProductApplicationFlow._application_response(context)
        context.result = build_product_application_result(
            ProductApplicationFlow._submission(context),
            ProductApplicationFlow._snapshot(context),
            flow_result={
                "applicationNo": application.data["applicationNo"],
                "flowTokenVersions": dict(context.flow_token_versions),
                "fixedTokenCall": "success",
            },
        )

    @staticmethod
    def report_execution_completed(progress: ProgressReporter | None) -> None:
        if progress is not None:
            progress(
                stage="execute",
                progress=90,
                message="产品申请处理完成，正在保存结果",
            )

    @staticmethod
    def result(context: ProductApplicationContext) -> dict[str, Any]:
        if context.result is None:
            raise RuntimeError("产品申请流程没有生成结果")
        return context.result

    @staticmethod
    def _submission(context: ProductApplicationContext) -> ProductApplicationSubmission:
        if context.submission is None:
            raise RuntimeError("产品申请流程尚未解析提交参数")
        return context.submission

    @staticmethod
    def _snapshot(context: ProductApplicationContext) -> ProductExecutionSnapshot:
        if context.execution_snapshot is None:
            raise RuntimeError("产品申请流程尚未解析执行配置")
        return context.execution_snapshot

    @staticmethod
    def _request_head(context: ProductApplicationContext):
        if context.request_head is None:
            raise RuntimeError("产品申请流程尚未创建请求头")
        return context.request_head

    @staticmethod
    def _application_response(context: ProductApplicationContext):
        if context.application_response is None:
            raise RuntimeError("产品申请流程尚未提交申请")
        return context.application_response
