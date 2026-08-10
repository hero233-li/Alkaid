from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.utils.http import config
from apps.utils.http.contracts import EndpointSpec

ProgressReporter = Callable[..., None]
RAW_MESSAGE_FILE = Path(__file__).parents[3] / "config" / "raw_messages" / "agreement.json"


class CjdkEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    rsp_body: dict[str, Any] = Field(alias="RSP_BODY")
    rsp_head: dict[str, Any] = Field(default_factory=dict, alias="RSP_HEAD")


def new_message(name: str) -> dict[str, Any]:
    try:
        return deepcopy(_agreement_messages()[name])
    except KeyError:
        raise KeyError(f"未配置协议原始报文：{name}") from None


@lru_cache(maxsize=1)
def _agreement_messages() -> dict[str, dict[str, Any]]:
    raw = json.loads(RAW_MESSAGE_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or any(not isinstance(value, dict) for value in raw.values()):
        raise ValueError("agreement.json 必须是以报文名称为键、JSON 对象为值的对象")
    return {str(name): message for name, message in raw.items()}


def validate_agreement_messages() -> dict[str, int]:
    catalog = _agreement_messages()
    required = {
        "query_agreement_templates_v1",
        "query_preview_image_v1",
        "show_document_by_doc_id_v1",
    }
    missing = required - catalog.keys()
    if missing:
        raise ValueError(f"缺少协议原始报文：{', '.join(sorted(missing))}")
    return {"messages": len(catalog)}


QUERY_AGREEMENT_TEMPLATES = EndpointSpec(
    **config.request_contract(
        "agreement",
        "queryTemplates",
        operation_id="cjdk_jyrc.query_agreement_templates",
        method="POST",
        path="/h5/microservice/queryAgreementTemplateInfoListEA.do",
    ),
    response_model=CjdkEnvelope,
)
QUERY_PREVIEW_IMAGE = EndpointSpec(
    **config.request_contract(
        "agreement",
        "queryPreview",
        operation_id="cjdk_jyrc.query_preview_image",
        method="POST",
        path="/h5/microservice/queryPreviewImage.ajax",
    ),
    response_model=CjdkEnvelope,
)
SHOW_DOCUMENT_BY_DOC_ID = EndpointSpec(
    **config.request_contract(
        "agreement",
        "readDocument",
        operation_id="cjdk_jyrc.show_document_by_doc_id",
        method="POST",
        path="/h5/microservice/showDocumentByDocIdList.ajax",
    ),
    response_model=CjdkEnvelope,
)


class CjdkProtocolError(RuntimeError):
    pass


def read_agreements(
    *,
    client: Any,
    settings: config.CjdkJyrcSettings,
    payload: Mapping[str, Any],
    scene: str | None = None,
    stage_prefix: str = "agreement",
    progress_points: tuple[int, int, int] = (65, 78, 90),
    progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    """Read the complete agreement set; callers only provide runtime dependencies."""

    query_progress, preview_progress, read_progress = progress_points
    templates = query_agreement_templates(client, settings, payload, scene=scene)
    _report(progress, f"{stage_prefix}_query", query_progress, "协议模板查询完成")
    preview = query_agreement_preview(client, settings, payload, templates)
    _report(progress, f"{stage_prefix}_preview", preview_progress, "协议预览生成完成")
    doc_ids = (
        (str(preview["docId"]),)
        if preview.get("docId")
        else tuple(
            str(document["docId"]) for document in preview["Documents"] if document.get("docId")
        )
    )
    if not doc_ids:
        raise RuntimeError("协议预览成功，但没有可用于读取协议的 docId")
    documents = read_agreement_documents(client, settings, doc_ids)
    _report(progress, f"{stage_prefix}_read", read_progress, "协议阅读完成")
    return {
        "agreementTemplates": templates,
        "agreementPreview": preview,
        "agreementDocuments": documents,
        "session": client.state,
    }


def query_agreement_templates(
    client: Any,
    settings: config.CjdkJyrcSettings,
    payload: Mapping[str, Any],
    *,
    scene: str | None = None,
) -> tuple[dict[str, Any], ...]:
    message = new_message("query_agreement_templates_v1")
    request = message["REQ_BODY"]["request"]
    product_id = _required_payload_text(payload, "product", "产品编号")
    cooperation_project_id = _optional_payload_text(payload, "cooperationProjectId")
    request.update(
        {
            "x-channel": config.channel(),
            "scene": scene or config.scene(),
            "selbProdId": product_id,
            "branchId": str(payload["branch"]),
            "prodSubdvDmsn": config.product_subdivision(),
        }
    )
    request.pop("prodSubdvDmsnEncode", None)
    if cooperation_project_id is not None:
        request["prodSubdvDmsnEncode"] = cooperation_project_id
    response = client.request(
        step="agreement.query_templates", endpoint=QUERY_AGREEMENT_TEMPLATES, message=message
    )
    response_data = required_mapping(response.rsp_body, "response")
    templates = required_list(response_data, "docAgreementTemplateInfoList")
    if not templates:
        raise CjdkProtocolError("查询协议成功，但未返回协议模板")
    limit = settings.response_limits.max_agreement_templates
    if len(templates) > limit:
        raise CjdkProtocolError(f"协议模板返回 {len(templates)} 个，超过上限 {limit}")
    return tuple(
        {
            "docId": required_text(item, "docId"),
            "docName": optional_text(item, "docName"),
            "docType": optional_text(item, "docType"),
            "fcosTemplateNo": optional_text(item, "fcosTemplateNo"),
            "status": optional_text(item, "status"),
        }
        for item in templates
    )


def query_agreement_preview(
    client: Any,
    settings: config.CjdkJyrcSettings,
    payload: Mapping[str, Any],
    templates: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    template_numbers = [
        str(item["fcosTemplateNo"]) for item in templates if item.get("fcosTemplateNo")
    ] or list(config.default_template_numbers())
    if not template_numbers:
        raise CjdkProtocolError("没有可用于生成协议预览的模板编号")
    message = new_message("query_preview_image_v1")
    request = message["REQ_BODY"]["request"]
    auth_values = {
        "custNme": str(payload.get("personName") or ""),
        "idNo": str(payload.get("certificateNo") or ""),
        "orgCode": str(payload.get("branch") or ""),
    }
    id_type = str(payload.get("idType") or config.default_id_type()).strip()
    if id_type:
        auth_values["idType"] = id_type
    request["authVariableList"] = [
        {
            **item,
            "value": auth_values.get(str(item.get("code") or ""), str(item.get("value") or "")),
        }
        for item in request.get("authVariableList", [])
    ]
    product_id = _required_payload_text(payload, "product", "产品编号")
    request.update(
        {
            "x-channel": config.channel(),
            "selbProdId": product_id,
            "businessNo": config.business_no(),
            "fcosTemplateNoList": [{"fcosTemplateNo": number} for number in template_numbers],
        }
    )
    cooperation_project_id = _optional_payload_text(payload, "cooperationProjectId")
    request.pop("coprProjeId", None)
    request.pop("prodSubdvDmsnEncode", None)
    if cooperation_project_id is not None:
        request["prodSubdvDmsnEncode"] = cooperation_project_id
    response = client.request(
        step="agreement.query_preview", endpoint=QUERY_PREVIEW_IMAGE, message=message
    )
    preview = required_mapping(response.rsp_body, "response")
    success_flag = required_text(preview, "successFlag")
    if success_flag != "Y":
        raise CjdkProtocolError(
            f"协议预览生成失败：{optional_text(preview, 'message') or success_flag}"
        )
    documents = required_list(preview, "docList", allow_missing=True)
    preview_doc_id = optional_text(preview, "docId")
    if not documents and preview_doc_id:
        documents.append({"docId": preview_doc_id})
    if not documents:
        raise CjdkProtocolError("协议预览成功，但未返回 docId")
    limit = settings.response_limits.max_preview_documents
    if len(documents) > limit:
        raise CjdkProtocolError(f"协议预览返回 {len(documents)} 个文档，超过上限 {limit}")
    return {
        "successFlag": success_flag,
        "docId": preview_doc_id,
        "Documents": tuple(
            {
                "docId": required_text(item, "docId"),
                "docName": optional_text(item, "docName"),
                "docType": optional_text(item, "docType"),
                "fcosTemplateNo": optional_text(item, "fcosTemplateNo"),
            }
            for item in documents
        ),
    }


def read_agreement_documents(
    client: Any,
    settings: config.CjdkJyrcSettings,
    doc_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    documents: list[dict[str, Any]] = []
    total_document_bytes = 0
    total_limit = settings.response_limits.max_total_document_bytes
    for doc_id in doc_ids:
        document = read_agreement_document(client, settings, doc_id)
        total_document_bytes += int(document.get("contentBytes") or 0)
        if total_document_bytes > total_limit:
            raise CjdkProtocolError(f"所有协议文档累计超过 {total_limit} bytes")
        documents.append(document)
    return tuple(documents)


def read_agreement_document(
    client: Any, settings: config.CjdkJyrcSettings, doc_id: str
) -> dict[str, Any]:
    message = new_message("show_document_by_doc_id_v1")
    message["REQ_BODY"]["request"].update(
        {"x-channel": config.channel(), "docId": doc_id, "TransCode": ""}
    )
    response = client.request(
        step="agreement.read_document", endpoint=SHOW_DOCUMENT_BY_DOC_ID, message=message
    )
    document = response.rsp_body
    success_flag = required_text(document, "successFlag")
    if success_flag != "Y":
        raise CjdkProtocolError(f"读取协议失败：successFlag={success_flag}")
    file_items = required_list(document, "fileInfo", allow_missing=True)
    file_info = file_items[0] if file_items else {}
    content = optional_text(document, "downFile") or optional_text(file_info, "downFile")
    if not content:
        raise CjdkProtocolError("读取协议成功，但未返回协议文件内容")
    content_bytes = validated_decoded_size(settings, doc_id, content)
    return {
        "docId": doc_id,
        "fileName": optional_text(file_info, "fileName"),
        "docSize": optional_text(document, "docSize"),
        "successFlag": success_flag,
        "contentBytes": content_bytes,
    }


def validated_decoded_size(settings: config.CjdkJyrcSettings, doc_id: str, content: str) -> int:
    limits = settings.response_limits
    if len(content) > limits.max_base64_characters:
        raise CjdkProtocolError(
            f"文档 {doc_id} Base64 字符长度超过上限 {limits.max_base64_characters}"
        )
    estimated = len(content) * 3 // 4
    if estimated > limits.max_decoded_document_bytes:
        raise CjdkProtocolError(
            f"文档 {doc_id} 解码后大小超过上限 {limits.max_decoded_document_bytes} bytes"
        )
    try:
        decoded_size = len(base64.b64decode(content, validate=True))
    except (ValueError, binascii.Error) as exc:
        raise CjdkProtocolError(f"文档 {doc_id} 不是有效 Base64") from exc
    if decoded_size > limits.max_decoded_document_bytes:
        raise CjdkProtocolError(
            f"文档 {doc_id} 解码后大小超过上限 {limits.max_decoded_document_bytes} bytes"
        )
    return decoded_size


def required_mapping(source: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = source.get(key)
    if not isinstance(value, Mapping):
        raise CjdkProtocolError(f"外系统响应缺少对象字段：{key}")
    return dict(value)


def required_list(
    source: Mapping[str, Any], key: str, *, allow_missing: bool = False
) -> list[dict[str, Any]]:
    value = source.get(key)
    if value is None and allow_missing:
        return []
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise CjdkProtocolError(f"外系统响应字段必须是对象列表：{key}")
    return [dict(item) for item in value]


def optional_text(source: Mapping[str, Any], key: str) -> str | None:
    value = source.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def required_text(source: Mapping[str, Any], key: str) -> str:
    value = optional_text(source, key)
    if value is None:
        raise CjdkProtocolError(f"外系统响应缺少文本字段：{key}")
    return value


def _optional_payload_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _required_payload_text(payload: Mapping[str, Any], key: str, label: str) -> str:
    value = _optional_payload_text(payload, key)
    if value is None:
        raise CjdkProtocolError(f"当前任务缺少{label}：{key}")
    return value


def _report(reporter: ProgressReporter | None, stage: str, progress: int, message: str) -> None:
    if reporter is not None:
        reporter(stage=stage, progress=progress, message=message)
