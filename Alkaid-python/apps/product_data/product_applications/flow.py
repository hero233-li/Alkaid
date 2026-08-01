from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from apps.product_data.catalog import ProductExecutionSnapshot
from apps.product_data.product_applications.context import ProductApplicationContext
from apps.product_data.product_applications.contracts import (
    AgreementPreviewResult,
    ApplicationLinkCommand,
    ApplicationLinksResult,
    ProductApplicationPort,
    SessionStatus,
)
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.services import (
    build_product_application_result,
    validate_submission,
)

ProgressReporter = Callable[..., None]


class ProductApplicationFlow:
    """Execute the fixed business order without knowing a concrete integration."""

    def __init__(self, port: ProductApplicationPort) -> None:
        self._port = port

    def execute(
        self,
        *,
        job_id: int,
        trace_id: str,
        submission: ProductApplicationSubmission,
        snapshot: ProductExecutionSnapshot,
        progress: ProgressReporter | None = None,
    ) -> dict[str, Any]:
        context = ProductApplicationContext(
            job_id=job_id,
            trace_id=trace_id,
            submission=submission,
            execution_snapshot=snapshot,
        )
        validate_submission(submission, execution_snapshot=snapshot)
        self._report(progress, "validate", 25, "产品申请参数校验完成")

        with self._port:
            self._generate_application_link(context)
            self._report(progress, "application_link", 40, "申请链接获取完成")
            self._initialize_session(context)
            if context.session.status != SessionStatus.ESTABLISHED:
                raise RuntimeError(
                    "外系统 Session 未满足配置要求，停止协议查询；"
                    f"当前状态={context.session.status.value}；"
                    f"缺少 Cookie={list(context.session.missing_cookies)}；"
                    f"缺少 Header={list(context.session.missing_headers)}；"
                    f"任一 Header 要求={list(context.session.missing_any_headers)}"
                )
            self._report(progress, "session", 50, "申请页面 Session 建立完成")
            context.agreement_templates = self._port.query_agreement_templates(
                context.submission.payload
            )
            self._report(progress, "agreement_query", 65, "协议模板查询完成")
            context.agreement_preview = self._port.query_agreement_preview(
                context.submission.payload, context.agreement_templates
            )
            self._report(progress, "agreement_preview", 78, "协议预览生成完成")
            context.agreement_documents = [
                self._port.read_agreement_document(document.doc_id)
                for document in self._preview(context).documents
            ]
            context.session = self._port.session_state()
            self._report(progress, "agreement_read", 90, "协议阅读完成，正在保存结果")

        self._build_result(context)
        if context.result is None:
            raise RuntimeError("产品申请流程没有生成结果")
        return context.result

    def _generate_application_link(self, context: ProductApplicationContext) -> None:
        route = context.execution_snapshot.application_link_route
        context.application_link_category = route.category_code.display_name
        context.application_links = self._port.generate_application_link(
            ApplicationLinkCommand(
                plan=route.model_dump(mode="json"),
                normalized_payload=deepcopy(context.execution_snapshot.normalized_payload),
            )
        )

    def _initialize_session(self, context: ProductApplicationContext) -> None:
        links = self._links(context)
        # URL selection is frozen into the task assembly settings, not inferred from payload.
        mode = getattr(self._port, "application_link_url_mode", "internal")
        application_url = links.internal_url if mode == "internal" else links.external_url
        context.selected_application_link_kind = mode
        context.session = self._port.initialize_session(application_url)

    @staticmethod
    def _build_result(context: ProductApplicationContext) -> None:
        preview = ProductApplicationFlow._preview(context)
        context.result = build_product_application_result(
            context.submission,
            context.execution_snapshot,
            flow_result={
                "message": "申请链接、Session、协议查询、预览与阅读完成",
                "applicationLink": {
                    "generated": context.application_links is not None,
                    "category": context.application_link_category,
                    "selected": context.selected_application_link_kind,
                },
                "agreementReadCompleted": bool(context.agreement_documents),
                "agreementTemplates": [
                    {
                        "docId": item.doc_id,
                        "docName": item.doc_name,
                        "docType": item.doc_type,
                        "fcosTemplateNo": item.fcos_template_no,
                        "status": item.status,
                    }
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
                    {
                        "docId": item.doc_id,
                        "fileName": item.file_name,
                        "docSize": item.declared_size,
                        "successFlag": item.success_flag,
                        "contentBytes": item.content_bytes,
                    }
                    for item in context.agreement_documents
                ],
                "externalSession": {
                    "status": context.session.status.value,
                    "established": context.session.status == SessionStatus.ESTABLISHED,
                    "cookieNames": list(context.session.cookie_names),
                    "forwardedHeaderNames": list(context.session.header_names),
                    "finalUrlPresent": context.session.final_url is not None,
                },
            },
        )

    @staticmethod
    def _links(context: ProductApplicationContext) -> ApplicationLinksResult:
        if context.application_links is None:
            raise RuntimeError("产品申请流程尚未获取申请链接")
        return context.application_links

    @staticmethod
    def _preview(context: ProductApplicationContext) -> AgreementPreviewResult:
        if context.agreement_preview is None:
            raise RuntimeError("产品申请流程尚未生成协议预览")
        return context.agreement_preview

    @staticmethod
    def _report(
        reporter: ProgressReporter | None, stage: str, progress: int, message: str
    ) -> None:
        if reporter:
            reporter(stage=stage, progress=progress, message=message)
