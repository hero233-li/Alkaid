import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.integrations.cjdk_jyrc.agreement_gateway import (
    AgreementProtocolError,
    CjdkAgreementGateway,
)
from apps.integrations.cjdk_jyrc.config import (
    CjdkJyrcSettings,
    EnvironmentSettings,
    JavaGatewaySettings,
    ResponseLimits,
)


class NullObserver:
    def request_started(self, **kwargs):
        return 1

    def request_finished(self, handle, **kwargs):
        return None

    def diagnostic(self, **kwargs):
        return None


def _gateway(**limit_updates) -> CjdkAgreementGateway:
    settings = CjdkJyrcSettings(
        mode="mock",
        application_link_url_mode="internal",
        java_gateway=JavaGatewaySettings(
            sdk_dir=Path("."),
            java_executable=Path("java"),
            jar=Path("application-link.jar"),
            main_class="mock.Main",
        ),
        environments={"UAT1": EnvironmentSettings(agreement_base_url="https://cjdk-jyrc.mock")},
        responseLimits=ResponseLimits().model_copy(update=limit_updates),
    )
    return CjdkAgreementGateway(
        settings=settings,
        client=SimpleNamespace(),  # type: ignore[arg-type]
    )


def test_template_and_preview_document_count_limits() -> None:
    gateway = _gateway(max_agreement_templates=1, max_preview_documents=1)
    templates = [
        SimpleNamespace(
            doc_id=str(index),
            doc_name=None,
            doc_type=None,
            fcos_template_no="T",
            status=None,
        )
        for index in range(2)
    ]
    gateway._client = SimpleNamespace(  # type: ignore[assignment]
        request=lambda **kwargs: SimpleNamespace(
            rsp_body=SimpleNamespace(response=SimpleNamespace(templates=templates))
        )
    )
    with pytest.raises(AgreementProtocolError, match="协议模板返回 2 个"):
        gateway.query_agreement_templates({"branch": "B"})

    preview_documents = [
        SimpleNamespace(doc_id=str(index), doc_name=None, doc_type=None, fcos_template_no="T")
        for index in range(2)
    ]
    gateway._client = SimpleNamespace(  # type: ignore[assignment]
        request=lambda **kwargs: SimpleNamespace(
            rsp_body=SimpleNamespace(
                response=SimpleNamespace(
                    success_flag="Y",
                    message=None,
                    doc_id=None,
                    documents=preview_documents,
                )
            )
        )
    )
    with pytest.raises(AgreementProtocolError, match="协议预览返回 2 个文档"):
        gateway.query_agreement_preview(
            {"branch": "B"},
            (SimpleNamespace(fcos_template_no="T"),),  # type: ignore[arg-type]
        )


def test_base64_character_decoded_and_total_limits() -> None:
    content = base64.b64encode(b"123456").decode()
    with pytest.raises(AgreementProtocolError, match="Base64 字符长度"):
        _gateway(max_base64_characters=4)._validated_decoded_size("DOC-1", content)
    with pytest.raises(AgreementProtocolError, match="解码后大小"):
        _gateway(max_decoded_document_bytes=4)._validated_decoded_size("DOC-1", content)

    gateway = _gateway(max_total_document_bytes=10)
    document = SimpleNamespace(
        success_flag="Y",
        file_info=[],
        down_file=content,
        doc_size="6",
    )
    gateway._client = SimpleNamespace(  # type: ignore[assignment]
        request=lambda **kwargs: SimpleNamespace(rsp_body=document)
    )
    with pytest.raises(AgreementProtocolError, match="累计超过"):
        gateway.read_agreement_documents(("DOC-1", "DOC-2"))
