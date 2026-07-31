import base64
import binascii
from collections.abc import Callable
from typing import Any

from apps.integrations.cjdk_jyrc.adapter import CjdkJyrcAgreementAdapter
from apps.integrations.cjdk_jyrc.models import (
    AgreementDocumentBody,
    AgreementPreviewData,
    AgreementTemplateInfo,
)
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
    """Run the implemented product flow in explicit Python order."""

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
        self.report_progress(
            progress,
            stage="validate",
            progress=35,
            message="产品申请参数校验完成",
        )

        with CjdkJyrcAgreementAdapter(
            job,
            environment=self.environment(context),
        ) as adapter:
            self.query_agreement_templates(context, adapter)
            self.report_progress(
                progress,
                stage="agreement_query",
                progress=55,
                message="协议模板查询完成",
            )

            self.query_agreement_preview(context, adapter)
            self.report_progress(
                progress,
                stage="agreement_preview",
                progress=70,
                message="协议预览生成完成",
            )

            self.read_agreement_documents(context, adapter)
            self.capture_session(context, adapter)
            self.report_progress(
                progress,
                stage="agreement_read",
                progress=90,
                message="协议阅读完成，正在保存结果",
            )

        self.build_result(context)
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
    def environment(context: ProductApplicationContext) -> str:
        value = ProductApplicationFlow._submission(context).payload.get("environment")
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError("产品申请环境不能为空")
        return value.strip()

    @staticmethod
    def query_agreement_templates(
        context: ProductApplicationContext,
        adapter: CjdkJyrcAgreementAdapter,
    ) -> None:
        context.agreement_templates = adapter.query_agreement_templates(
            ProductApplicationFlow._submission(context).payload
        )

    @staticmethod
    def query_agreement_preview(
        context: ProductApplicationContext,
        adapter: CjdkJyrcAgreementAdapter,
    ) -> None:
        context.agreement_preview = adapter.query_preview(
            ProductApplicationFlow._submission(context).payload,
            context.agreement_templates,
        )

    @staticmethod
    def read_agreement_documents(
        context: ProductApplicationContext,
        adapter: CjdkJyrcAgreementAdapter,
    ) -> None:
        preview = ProductApplicationFlow._agreement_preview(context)
        context.agreement_documents = [
            adapter.read_document(document.doc_id)
            for document in preview.documents
        ]

    @staticmethod
    def capture_session(
        context: ProductApplicationContext,
        adapter: CjdkJyrcAgreementAdapter,
    ) -> None:
        context.session_established = adapter.session_established
        context.session_header_names = adapter.session_header_names

    @staticmethod
    def build_result(context: ProductApplicationContext) -> None:
        preview = ProductApplicationFlow._agreement_preview(context)
        context.result = build_product_application_result(
            ProductApplicationFlow._submission(context),
            ProductApplicationFlow._snapshot(context),
            flow_result={
                "message": "协议查询、预览与阅读完成",
                "agreementReadCompleted": bool(context.agreement_documents),
                "agreementTemplates": [
                    ProductApplicationFlow._template_summary(item)
                    for item in context.agreement_templates
                ],
                "agreementPreview": {
                    "successFlag": preview.success_flag,
                    "docId": preview.doc_id,
                    "documents": [
                        {
                            "docId": item.doc_id,
                            "docName": item.doc_name,
                            "docType": item.doc_type,
                            "fcosTemplateNo": item.fcos_template_no,
                        }
                        for item in preview.documents
                    ],
                },
                "agreementDocuments": [
                    ProductApplicationFlow._document_summary(document)
                    for document in context.agreement_documents
                ],
                "externalSession": {
                    "established": context.session_established,
                    "forwardedHeaderNames": list(context.session_header_names),
                },
            },
        )

    @staticmethod
    def report_progress(
        progress_reporter: ProgressReporter | None,
        *,
        stage: str,
        progress: int,
        message: str,
    ) -> None:
        if progress_reporter is not None:
            progress_reporter(
                stage=stage,
                progress=progress,
                message=message,
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
    def _agreement_preview(context: ProductApplicationContext) -> AgreementPreviewData:
        if context.agreement_preview is None:
            raise RuntimeError("产品申请流程尚未生成协议预览")
        return context.agreement_preview

    @staticmethod
    def _template_summary(item: AgreementTemplateInfo) -> dict[str, Any]:
        return {
            "docId": item.doc_id,
            "docName": item.doc_name,
            "docType": item.doc_type,
            "fcosTemplateNo": item.fcos_template_no,
            "status": item.status,
        }

    @staticmethod
    def _document_summary(document: AgreementDocumentBody) -> dict[str, Any]:
        file_info = document.file_info[0] if document.file_info else None
        content = document.down_file or (file_info.down_file if file_info else None)
        return {
            "docId": (document.request or {}).get("docId"),
            "fileName": file_info.file_name if file_info else None,
            "docSize": document.doc_size,
            "successFlag": document.success_flag,
            "contentBytes": ProductApplicationFlow._decoded_size(content),
        }

    @staticmethod
    def _decoded_size(content: str | None) -> int | None:
        if not content:
            return None
        try:
            return len(base64.b64decode(content, validate=False))
        except (ValueError, binascii.Error):
            return None
