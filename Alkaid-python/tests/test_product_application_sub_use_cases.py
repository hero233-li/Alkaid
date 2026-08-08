import pytest

import apps.product_applications.cjdk.identity as identity_module
from apps.product_applications.api import ProductApplicationSubmission
from apps.product_applications.cjdk import config
from apps.product_applications.cjdk.identity import IdentityFlowError
from apps.product_applications.cjdk.runtime import (
    SessionState,
    SessionStatus,
    compile_application_link_plan,
)
from apps.product_applications.workflow import (
    execute_product_application,
    freeze_product_execution_snapshot,
)
from apps.product_data.catalog import load_product_catalog


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
        plan_compiler=compile_application_link_plan,
    )


class FakePorts:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def __enter__(self):
        self.calls.append("runtime.enter")
        return self

    def __exit__(self, *args):
        self.calls.append("runtime.exit")

    def open_application(self, **kwargs):
        self.calls.append("application.open")
        return {
            "applicationLinkCategory": "太阳码",
            "selectedApplicationLinkKind": "internal",
            "session": self._session(),
        }

    def read_agreements(self, **kwargs):
        self.calls.append("agreement.read")
        return {
            "agreementTemplates": (
                {
                    "docId": "TEMPLATE-1",
                    "docName": "测试协议",
                    "docType": "PDF",
                    "fcosTemplateNo": "FCOS-1",
                    "status": "ACTIVE",
                },
            ),
            "agreementPreview": {
                "successFlag": "Y",
                "docId": "DOC-1",
                "documents": (
                    {
                        "docId": "DOC-1",
                        "docName": "测试协议",
                        "docType": "PDF",
                        "fcosTemplateNo": "FCOS-1",
                    },
                ),
            },
            "agreementDocuments": (
                {
                    "docId": "DOC-1",
                    "fileName": "agreement.pdf",
                    "docSize": "6",
                    "successFlag": "Y",
                    "contentBytes": 6,
                },
            ),
            "session": self._session(),
        }

    def submit_application(self, **kwargs):
        self.calls.append("application.submit")
        return ("APPLY-1", "ENC-NAME", "ENC-ID")

    def verify_identity(self, **kwargs):
        self.calls.append("identity.verify")

    @staticmethod
    def _session():
        return SessionState(
            status=SessionStatus.ESTABLISHED,
            cookie_names=("JSESSIONID",),
            header_names=("X-Token",),
            final_url="https://example.test/internal",
        )


def test_top_level_uses_four_business_phases_and_preserves_result() -> None:
    submission, snapshot = _prepared()
    calls: list[str] = []
    result = execute_product_application(
        runtime=FakePorts(calls),
        submission=submission,
        snapshot=snapshot,
        application_link_kind="internal",
    )

    assert calls == [
        "runtime.enter",
        "application.open",
        "agreement.read",
        "application.submit",
        "identity.verify",
        "runtime.exit",
    ]
    assert result["identityVerificationCompleted"] is True
    assert result["agreementDocuments"][0]["contentBytes"] == 6


def _identity_dependencies(monkeypatch, *, face_status="N", verification_success=True):
    monkeypatch.setattr(
        identity_module, "get_public_key", lambda *args, **kwargs: ("MOCK-PUBLIC", "FLOW")
    )
    monkeypatch.setattr(identity_module, "get_prepare_mobile", lambda *args, **kwargs: "ENC-MOBILE")
    monkeypatch.setattr(
        identity_module, "get_ali_sdk_params", lambda *args, **kwargs: ("TRACE", "LICENSE")
    )
    monkeypatch.setattr(
        identity_module,
        "ali_video_check",
        lambda *args, **kwargs: {"status": face_status, "captchaTraceId": "CAPTCHA"},
    )
    monkeypatch.setattr(identity_module, "send_sms_code", lambda *args, **kwargs: (None, "PASS"))
    monkeypatch.setattr(identity_module, "check_sms_code", lambda *args, **kwargs: "SMS")
    monkeypatch.setattr(
        identity_module,
        "verify_identity_card",
        lambda *args, **kwargs: {
            "success": verification_success,
            "message": "最终身份验证失败" if not verification_success else None,
        },
    )


def _execute_identity(monkeypatch, *, sms_lookup=None, **updates):
    _identity_dependencies(monkeypatch, **updates)
    submission, _ = _prepared()
    identity_module.execute_identity_verification(
        client=object(),
        settings=config._mock_identity_settings(),
        payload=submission.payload,
        environment="UAT1",
        submission=("APPLY-1", "ENC-NAME", "ENC-ID"),
        read_agreements=lambda **kwargs: {},
        delete_photo=lambda **kwargs: None,
        find_sms_code=sms_lookup or (lambda **kwargs: "123456"),
        face_check_max_attempts=2,
    )


def test_identity_face_polling_stops_at_limit(monkeypatch) -> None:
    with pytest.raises(IdentityFlowError, match="轮询上限"):
        _execute_identity(monkeypatch, face_status="S")


def test_final_identity_verification_failure_fails_workflow(monkeypatch) -> None:
    with pytest.raises(IdentityFlowError, match="最终身份验证失败"):
        _execute_identity(monkeypatch, verification_success=False)


def test_identity_sms_lookup_failure_is_not_skipped(monkeypatch) -> None:
    def fail(**kwargs):
        raise RuntimeError("短信查询失败")

    with pytest.raises(RuntimeError, match="短信查询失败"):
        _execute_identity(monkeypatch, sms_lookup=fail)


def test_identity_sms_encryption_failure_is_not_skipped(monkeypatch) -> None:
    monkeypatch.setattr(
        identity_module,
        "encrypt_sms_code",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("短信加密失败")),
    )
    with pytest.raises(RuntimeError, match="短信加密失败"):
        _execute_identity(monkeypatch)
