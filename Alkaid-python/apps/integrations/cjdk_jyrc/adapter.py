from typing import Any

from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.api import (
    QUERY_AGREEMENT_TEMPLATES,
    QUERY_PREVIEW_IMAGE,
    SHOW_DOCUMENT_BY_DOC_ID,
)
from apps.integrations.cjdk_jyrc.client import CjdkJyrcClient
from apps.integrations.cjdk_jyrc.messages import new_message
from apps.integrations.cjdk_jyrc.models import (
    AgreementDocumentBody,
    AgreementPreviewData,
    AgreementPreviewDocument,
    AgreementTemplateInfo,
)
from apps.jobs.models import Job


class AgreementProtocolError(RuntimeError):
    pass


class CjdkJyrcAgreementAdapter:
    def __init__(self, job: Job, environment: str) -> None:
        self._client = CjdkJyrcClient(job, environment)

    def __enter__(self) -> "CjdkJyrcAgreementAdapter":
        self._client.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._client.__exit__(*args)

    @property
    def session_established(self) -> bool:
        return self._client.session_established

    @property
    def session_header_names(self) -> tuple[str, ...]:
        return self._client.session_header_names

    def query_agreement_templates(
        self,
        payload: dict[str, Any],
    ) -> list[AgreementTemplateInfo]:
        message = new_message("query_agreement_templates_v1")
        request = message["REQ_BODY"]["request"]
        request.update(
            {
                "x-channel": config.channel(),
                "scene": config.scene(),
                "selbProdId": config.product_id(),
                "branchId": str(payload["branch"]),
                "prodSubdvDmsn": config.product_subdivision(),
                "prodSubdvDmsnEncode": config.product_subdivision_encode(),
            }
        )
        response = self._client.request(
            step="agreement.query_templates",
            endpoint=QUERY_AGREEMENT_TEMPLATES,
            message=message,
        )
        templates = response.rsp_body.response.templates
        if not templates:
            raise AgreementProtocolError("查询协议成功，但未返回协议模板")
        return templates

    def query_preview(
        self,
        payload: dict[str, Any],
        templates: list[AgreementTemplateInfo],
    ) -> AgreementPreviewData:
        template_numbers = [
            item.fcos_template_no
            for item in templates
            if item.fcos_template_no
        ] or list(config.default_template_numbers())
        if not template_numbers:
            raise AgreementProtocolError("没有可用于生成协议预览的模板编号")

        message = new_message("query_preview_image_v1")
        request = message["REQ_BODY"]["request"]
        auth_values = {
            "custNme": str(payload.get("personName") or ""),
            "idNo": str(payload.get("certificateNo") or ""),
            "idType": str(payload.get("idType") or config.default_id_type()),
            "orgCode": str(payload.get("branch") or ""),
        }
        request.update(
            {
                "x-channel": config.channel(),
                "authVariableList": [
                    {"code": code, "value": value}
                    for code, value in auth_values.items()
                ],
                "selbProdId": config.product_id(),
                "businessNo": config.business_no(),
                "fcosTemplateNoList": [
                    {"fcosTemplateNo": number}
                    for number in template_numbers
                ],
                "coprProjeId": str(
                    payload.get("projectId") or config.default_project_id()
                ),
                "prodSubdvDmsnEncode": config.product_subdivision_encode(),
            }
        )
        response = self._client.request(
            step="agreement.query_preview",
            endpoint=QUERY_PREVIEW_IMAGE,
            message=message,
        )
        preview = response.rsp_body.response
        if preview.success_flag != "Y":
            raise AgreementProtocolError(
                f"协议预览生成失败：{preview.message or preview.success_flag}"
            )
        if not preview.documents and preview.doc_id:
            preview.documents.append(
                AgreementPreviewDocument(
                    docId=preview.doc_id,
                )
            )
        if not preview.documents:
            raise AgreementProtocolError("协议预览成功，但未返回 docId")
        return preview

    def read_document(self, doc_id: str) -> AgreementDocumentBody:
        message = new_message("show_document_by_doc_id_v1")
        request = message["REQ_BODY"]["request"]
        request.update(
            {
                "x-channel": config.channel(),
                "docId": doc_id,
                "TransCode": "",
            }
        )
        response = self._client.request(
            step="agreement.read_document",
            endpoint=SHOW_DOCUMENT_BY_DOC_ID,
            message=message,
        )
        document = response.rsp_body
        if document.success_flag != "Y":
            raise AgreementProtocolError(
                f"读取协议失败：successFlag={document.success_flag}"
            )
        if not document.down_file and not any(
            item.down_file for item in document.file_info
        ):
            raise AgreementProtocolError("读取协议成功，但未返回协议文件内容")
        return document
