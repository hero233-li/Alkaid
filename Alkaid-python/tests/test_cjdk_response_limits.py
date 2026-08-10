import base64
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from apps.utils.http.config import (
    CjdkJyrcSettings,
    EnvironmentSettings,
)
from apps.workflow.product_applications.cjdk.client import validate_cjdk_business_response
from apps.workflow.product_applications.common.agreement import (
    CjdkEnvelope,
    CjdkProtocolError,
    query_agreement_preview,
    query_agreement_templates,
    read_agreement_documents,
    validated_decoded_size,
)


class NullObserver:
    def request_started(self, **kwargs):
        return 1

    def request_finished(self, handle, **kwargs):
        return None

    def diagnostic(self, **kwargs):
        return None


def _settings(**limit_updates) -> CjdkJyrcSettings:
    settings = CjdkJyrcSettings(
        mode="mock",
        application_link_url_mode="internal",
        environments={"UAT1": EnvironmentSettings(agreement_base_url="https://cjdk-jyrc.mock")},
        **limit_updates,
    )
    return settings


def test_template_and_preview_document_count_limits() -> None:
    settings = _settings(max_agreement_templates=1, max_preview_documents=1)
    templates = [
        SimpleNamespace(
            docId=str(index),
            docName=None,
            docType=None,
            fcosTemplateNo="T",
            status=None,
        )
        for index in range(2)
    ]
    client = SimpleNamespace(
        request=lambda **kwargs: SimpleNamespace(
            rsp_body={"response": {"docAgreementTemplateInfoList": [vars(x) for x in templates]}}
        )
    )
    with pytest.raises(CjdkProtocolError, match="协议模板返回 2 个"):
        query_agreement_templates(client, settings, {"branch": "B", "product": "P"})

    preview_documents = [
        {"docId": str(index), "docName": None, "docType": None, "fcosTemplateNo": "T"}
        for index in range(2)
    ]
    client = SimpleNamespace(
        request=lambda **kwargs: SimpleNamespace(
            rsp_body={"response": {"successFlag": "Y", "docList": preview_documents}}
        )
    )
    with pytest.raises(CjdkProtocolError, match="协议预览返回 2 个文档"):
        query_agreement_preview(
            client,
            settings,
            {"branch": "B", "product": "P"},
            ({"fcosTemplateNo": "T"},),
        )


def test_base64_character_decoded_and_total_limits() -> None:
    content = base64.b64encode(b"123456").decode()
    with pytest.raises(CjdkProtocolError, match="Base64 字符长度"):
        validated_decoded_size(_settings(max_base64_characters=4), "DOC-1", content)
    with pytest.raises(CjdkProtocolError, match="解码后大小"):
        validated_decoded_size(_settings(max_decoded_document_bytes=4), "DOC-1", content)

    settings = _settings(max_total_document_bytes=10)
    document = {"successFlag": "Y", "fileInfo": [], "downFile": content, "docSize": "6"}
    client = SimpleNamespace(request=lambda **kwargs: SimpleNamespace(rsp_body=document))
    with pytest.raises(CjdkProtocolError, match="累计超过"):
        read_agreement_documents(client, settings, ("DOC-1", "DOC-2"))


def test_unified_envelope_validates_shape_and_preserves_raw_fields() -> None:
    raw = {
        "RSP_BODY": {"response": {"base64": "AAEC"}, "vendorExtension": {"x": 1}},
        "RSP_HEAD": {"PROCESS_STATUS_CODE": "N"},
        "topLevelExtension": "kept",
    }
    envelope = CjdkEnvelope.model_validate(raw)

    assert envelope.rsp_body == raw["RSP_BODY"]
    assert envelope.rsp_head == raw["RSP_HEAD"]
    assert envelope.model_dump(by_alias=True)["topLevelExtension"] == "kept"

    with pytest.raises(ValidationError):
        CjdkEnvelope.model_validate({"RSP_HEAD": {}})
    with pytest.raises(ValidationError):
        CjdkEnvelope.model_validate({"RSP_BODY": []})


def test_unified_boundary_rejects_business_failure() -> None:
    with pytest.raises(RuntimeError, match="业务处理失败"):
        validate_cjdk_business_response(
            {"biz_state": "FAIL", "rsp_code": "E001", "rsp_msg": "rejected"}
        )
