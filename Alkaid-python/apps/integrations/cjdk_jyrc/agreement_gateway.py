from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from typing import Any

from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.api import (
    QUERY_AGREEMENT_TEMPLATES,
    QUERY_PREVIEW_IMAGE,
    SHOW_DOCUMENT_BY_DOC_ID,
)
from apps.integrations.cjdk_jyrc.client import CjdkJyrcClient
from apps.integrations.cjdk_jyrc.messages import new_message
from apps.integrations.cjdk_jyrc.models import AgreementPreviewDocument
from apps.product_data.product_applications.contracts import (
    AgreementDocumentResult,
    AgreementPreviewDocumentResult,
    AgreementPreviewResult,
    AgreementTemplateResult,
)


class AgreementProtocolError(RuntimeError):
    pass


class CjdkAgreementGateway:
    def __init__(
        self,
        *,
        settings: config.CjdkJyrcSettings,
        client: CjdkJyrcClient,
    ) -> None:
        self._settings = settings
        self._client = client

    def query_agreement_templates(
        self, payload: Mapping[str, Any]
    ) -> tuple[AgreementTemplateResult, ...]:
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
        limit = self._settings.response_limits.max_agreement_templates
        if len(templates) > limit:
            raise AgreementProtocolError(f"协议模板返回 {len(templates)} 个，超过上限 {limit}")
        return tuple(
            AgreementTemplateResult(
                doc_id=item.doc_id,
                doc_name=item.doc_name,
                doc_type=item.doc_type,
                fcos_template_no=item.fcos_template_no,
                status=item.status,
            )
            for item in templates
        )

    def query_agreement_preview(
        self,
        payload: Mapping[str, Any],
        templates: tuple[AgreementTemplateResult, ...],
    ) -> AgreementPreviewResult:
        template_numbers = [
            item.fcos_template_no for item in templates if item.fcos_template_no
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
                    {"code": code, "value": value} for code, value in auth_values.items()
                ],
                "selbProdId": config.product_id(),
                "businessNo": config.business_no(),
                "fcosTemplateNoList": [{"fcosTemplateNo": number} for number in template_numbers],
                "coprProjeId": str(
                    payload.get("projectId")
                    or payload.get("cooperationProjectId")
                    or config.default_project_id()
                ),
                "prodSubdvDmsnEncode": config.product_subdivision_encode(),
            }
        )
        response = self._client.request(
            step="agreement.query_preview", endpoint=QUERY_PREVIEW_IMAGE, message=message
        )
        preview = response.rsp_body.response
        if preview.success_flag != "Y":
            raise AgreementProtocolError(
                f"协议预览生成失败：{preview.message or preview.success_flag}"
            )
        documents = list(preview.documents)
        if not documents and preview.doc_id:
            documents.append(AgreementPreviewDocument(docId=preview.doc_id))
        if not documents:
            raise AgreementProtocolError("协议预览成功，但未返回 docId")
        limit = self._settings.response_limits.max_preview_documents
        if len(documents) > limit:
            raise AgreementProtocolError(f"协议预览返回 {len(documents)} 个文档，超过上限 {limit}")
        return AgreementPreviewResult(
            success_flag=preview.success_flag,
            doc_id=preview.doc_id,
            documents=tuple(
                AgreementPreviewDocumentResult(
                    doc_id=item.doc_id,
                    doc_name=item.doc_name,
                    doc_type=item.doc_type,
                    fcos_template_no=item.fcos_template_no,
                )
                for item in documents
            ),
        )

    def read_agreement_documents(
        self, doc_ids: tuple[str, ...]
    ) -> tuple[AgreementDocumentResult, ...]:
        documents: list[AgreementDocumentResult] = []
        total_document_bytes = 0
        total_limit = self._settings.response_limits.max_total_document_bytes
        for doc_id in doc_ids:
            document = self._read_agreement_document(doc_id)
            total_document_bytes += document.content_bytes or 0
            if total_document_bytes > total_limit:
                raise AgreementProtocolError(f"所有协议文档累计超过 {total_limit} bytes")
            documents.append(document)
        return tuple(documents)

    def _read_agreement_document(self, doc_id: str) -> AgreementDocumentResult:
        message = new_message("show_document_by_doc_id_v1")
        message["REQ_BODY"]["request"].update(
            {"x-channel": config.channel(), "docId": doc_id, "TransCode": ""}
        )
        response = self._client.request(
            step="agreement.read_document",
            endpoint=SHOW_DOCUMENT_BY_DOC_ID,
            message=message,
        )
        document = response.rsp_body
        if document.success_flag != "Y":
            raise AgreementProtocolError(f"读取协议失败：successFlag={document.success_flag}")
        file_info = document.file_info[0] if document.file_info else None
        content = document.down_file or (file_info.down_file if file_info else None)
        if not content:
            raise AgreementProtocolError("读取协议成功，但未返回协议文件内容")
        content_bytes = self._validated_decoded_size(doc_id, content)
        return AgreementDocumentResult(
            doc_id=doc_id,
            file_name=file_info.file_name if file_info else None,
            declared_size=document.doc_size,
            success_flag=document.success_flag,
            content_bytes=content_bytes,
        )

    def _validated_decoded_size(self, doc_id: str, content: str) -> int:
        limits = self._settings.response_limits
        if len(content) > limits.max_base64_characters:
            raise AgreementProtocolError(
                f"文档 {doc_id} Base64 字符长度超过上限 {limits.max_base64_characters}"
            )
        estimated = (len(content) * 3) // 4
        if estimated > limits.max_decoded_document_bytes:
            raise AgreementProtocolError(
                f"文档 {doc_id} 解码后大小超过 {limits.max_decoded_document_bytes} bytes"
            )
        try:
            decoded_size = len(base64.b64decode(content, validate=True))
        except (ValueError, binascii.Error) as exc:
            raise AgreementProtocolError(f"文档 {doc_id} 不是有效 Base64") from exc
        if decoded_size > limits.max_decoded_document_bytes:
            raise AgreementProtocolError(
                f"文档 {doc_id} 解码后大小超过 {limits.max_decoded_document_bytes} bytes"
            )
        return decoded_size
