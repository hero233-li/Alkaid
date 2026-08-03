from dataclasses import FrozenInstanceError

import pytest

from apps.product_data.catalog import load_product_catalog
from apps.product_data.product_applications.agreement_use_case import (
    query_preview_and_read_agreements,
)
from apps.product_data.product_applications.application_link_use_case import (
    generate_application_link_and_establish_session,
)
from apps.product_data.product_applications.contracts import (
    AgreementDocumentResult,
    AgreementPreviewDocumentResult,
    AgreementPreviewResult,
    AgreementTemplateResult,
    ApplicationLinksResult,
    SessionState,
    SessionStatus,
)
from apps.product_data.product_applications.preparation import freeze_product_execution_snapshot
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.use_cases import execute_product_application


def _prepared():
    return freeze_product_execution_snapshot(
        ProductApplicationSubmission(
            name="产品B申请",
            product="product-b",
            payload={
                "environment": "UAT1",
                "product": "product-b",
                "location": "example-location",
                "branch": "example-branch",
                "outlet": "example-outlet",
                "personName": "测试用户",
                "certificateNo": "330101199001011234",
                "cardNo": "6222000000000000",
                "phone": "13800138000",
                "customerType": "farmer",
                "applicationMethod": "normal",
                "redShieldEnabled": True,
            },
        ),
        load_product_catalog(),
    )


class FakeRuntime:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def __enter__(self):
        self._calls.append("runtime.enter")
        return self

    def __exit__(self, *args):
        self._calls.append("runtime.exit")


class FakeApplicationLinkGateway:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def generate_application_link(self, command):
        self._calls.append("application_link.generate")
        return ApplicationLinksResult(
            internal_url="https://example.test/internal",
            external_url="https://example.test/external",
        )


class FakeExternalSessionGateway:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls
        self._state = SessionState(
            status=SessionStatus.ESTABLISHED,
            cookie_names=("JSESSIONID",),
            header_names=("X-Token",),
            final_url="https://example.test/internal",
        )

    def initialize_session(self, application_url):
        self._calls.append("session.initialize")
        return self._state

    def session_state(self):
        self._calls.append("session.state")
        return self._state


class FakeAgreementGateway:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def query_agreement_templates(self, payload):
        self._calls.append("agreement.templates")
        return (
            AgreementTemplateResult(
                doc_id="TEMPLATE-1",
                doc_name="测试协议",
                doc_type="PDF",
                fcos_template_no="FCOS-1",
                status="ACTIVE",
            ),
        )

    def query_agreement_preview(self, payload, templates):
        self._calls.append("agreement.preview")
        return AgreementPreviewResult(
            success_flag="Y",
            doc_id="DOC-1",
            documents=(
                AgreementPreviewDocumentResult(
                    doc_id="DOC-1",
                    doc_name="测试协议",
                    doc_type="PDF",
                    fcos_template_no="FCOS-1",
                ),
            ),
        )

    def read_agreement_documents(self, doc_ids):
        self._calls.append("agreement.documents")
        assert doc_ids == ("DOC-1",)
        return (
            AgreementDocumentResult(
                doc_id="DOC-1",
                file_name="agreement.pdf",
                declared_size="6",
                success_flag="Y",
                content_bytes=6,
            ),
        )


def test_sub_use_cases_return_frozen_typed_outcomes() -> None:
    prepared = _prepared()
    calls: list[str] = []
    sessions = FakeExternalSessionGateway(calls)
    link_outcome = generate_application_link_and_establish_session(
        application_links=FakeApplicationLinkGateway(calls),
        external_session=sessions,
        snapshot=prepared.snapshot,
        application_link_kind="internal",
    )
    agreement_outcome = query_preview_and_read_agreements(
        agreements=FakeAgreementGateway(calls),
        external_session=sessions,
        payload=prepared.submission.payload,
    )

    assert link_outcome.application_links.internal_url.endswith("/internal")
    assert agreement_outcome.agreement_documents[0].content_bytes == 6
    with pytest.raises(FrozenInstanceError):
        link_outcome.application_link_category = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        agreement_outcome.agreement_documents = ()  # type: ignore[misc]


def test_top_level_preserves_call_order_and_complete_result_contract() -> None:
    prepared = _prepared()
    calls: list[str] = []
    sessions = FakeExternalSessionGateway(calls)
    result = execute_product_application(
        runtime=FakeRuntime(calls),
        application_links=FakeApplicationLinkGateway(calls),
        external_session=sessions,
        agreements=FakeAgreementGateway(calls),
        submission=prepared.submission,
        snapshot=prepared.snapshot,
        application_link_kind="internal",
    )

    assert calls == [
        "runtime.enter",
        "application_link.generate",
        "session.initialize",
        "agreement.templates",
        "agreement.preview",
        "agreement.documents",
        "session.state",
        "runtime.exit",
    ]
    assert result == {
        "validated": True,
        "product": "product-b",
        "productType": prepared.snapshot.product_type,
        "customerType": "farmer",
        "switch": prepared.snapshot.switch_field,
        "switchEnabled": True,
        "executionConfigVersion": prepared.snapshot.catalog_version,
        "applicationMethod": "normal",
        "executionFields": list(prepared.snapshot.fields),
        "message": "申请链接、Session、协议查询、预览与阅读完成",
        "applicationLink": {"generated": True, "category": "太阳码", "selected": "internal"},
        "agreementReadCompleted": True,
        "agreementTemplates": [
            {
                "docId": "TEMPLATE-1",
                "docName": "测试协议",
                "docType": "PDF",
                "fcosTemplateNo": "FCOS-1",
                "status": "ACTIVE",
            }
        ],
        "agreementPreview": {
            "successFlag": "Y",
            "docId": "DOC-1",
            "documents": [
                {
                    "docId": "DOC-1",
                    "docName": "测试协议",
                    "docType": "PDF",
                    "fcosTemplateNo": "FCOS-1",
                }
            ],
        },
        "agreementDocuments": [
            {
                "docId": "DOC-1",
                "fileName": "agreement.pdf",
                "docSize": "6",
                "successFlag": "Y",
                "contentBytes": 6,
            }
        ],
        "externalSession": {
            "status": "established",
            "established": True,
            "cookieNames": ["JSESSIONID"],
            "forwardedHeaderNames": ["X-Token"],
            "finalUrlPresent": True,
        },
    }
