import pytest

import apps.workflow.product_applications.identity.identity as identity_module
from apps.utils.application_links import compile_application_link_plan
from apps.utils.http import config
from apps.utils.product_Conf.catalog import ProductWorkflowStep, load_product_catalog
from apps.workflow.product_applications.api import ProductApplicationSubmission
from apps.workflow.product_applications.cjdk.client import (
    SessionState,
    SessionStatus,
)
from apps.workflow.product_applications.contracts import SubmittedApplication
from apps.workflow.product_applications.identity.identity import IdentityFlowError
from apps.workflow.product_applications.workflow import (
    execute_product_application,
    freeze_product_execution_snapshot,
)
from apps.workflow.product_applications.workflow_engine import ProductWorkflowConfigurationError


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
        self.client = self
        self.settings = None
        self.observer = None
        self.trace_id = "test"
        self.identity_settings = None
        self.photo_client = None
        self.dcpp_client = None

    def open(self):
        self.calls.append("runtime.open")

    def close(self):
        self.calls.append("runtime.close")

    def execute_application(self, **kwargs):
        self.calls.append("application.execute")
        return {
            "applicationLinkCategory": "太阳码",
            "selectedApplicationLinkKind": "internal",
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
                "Documents": (
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
            "submittedApplication": SubmittedApplication(
                application_id="APPLY-1",
                encrypted_customer_name="ENC-NAME",
                encrypted_identity_no="ENC-ID",
            ),
        }

    def verify_identity(self, **kwargs):
        self.calls.append("identity.verify")
        assert kwargs["submission"] == SubmittedApplication(
            application_id="APPLY-1",
            encrypted_customer_name="ENC-NAME",
            encrypted_identity_no="ENC-ID",
        )
        return {
            "application_id": "APPLY-1",
            "product_id": "product-b",
            "plain_customer_name": "测试用户",
            "plain_identity_no": "330101199001011234",
            "plain_mobile": "13800138000",
            "encrypted_customer_name": "ENC-NAME",
            "encrypted_identity_no": "ENC-ID",
            "branch_no": "example-branch",
            "card_no": "6222000000000000",
            "public_key": "PUBLIC-KEY",
            "crypt_flow_no": "CRYPT-FLOW",
            "encrypted_mobile": "ENC-MOBILE",
            "trace_number": "TRACE-NUMBER",
            "license": "LICENSE",
            "captcha_trace_id": "CAPTCHA-TRACE",
            "face_verify_status": "N",
            "face_verify_message": "人脸认证成功",
            "face_check_attempts": 1,
            "pass_code_seq": "PASS-CODE-SEQ",
            "sms_code": "123456",
            "encrypted_sms_code": "ENC-SMS-CODE",
            "sms_message_id": "SMS-MESSAGE-ID",
            "verification": {
                "success": True,
                "message": "身份认证成功",
                "rawResponse": {"verified": True},
            },
        }

    @staticmethod
    def _session():
        return SessionState(
            status=SessionStatus.ESTABLISHED,
            cookie_names=("JSESSIONID",),
            header_names=("X-Token",),
            final_url="https://example.test/internal",
        )


def _wire_fake_flows(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.workflow.product_applications.modules.application.execute_application",
        lambda client, **kwargs: client.execute_application(**kwargs),
    )
    monkeypatch.setattr(
        "apps.workflow.product_applications.modules.identity.execute_identity_verification",
        lambda client, **kwargs: client.verify_identity(**kwargs),
    )


def test_top_level_executes_application_then_identity(monkeypatch) -> None:
    _wire_fake_flows(monkeypatch)
    submission, snapshot = _prepared()
    calls: list[str] = []
    result = execute_product_application(
        runtime=FakePorts(calls),
        submission=submission,
        snapshot=snapshot,
        application_link_kind="internal",
    )

    assert calls == [
        "runtime.open",
        "application.execute",
        "identity.verify",
        "runtime.close",
    ]
    assert result["identityVerificationCompleted"] is True
    assert result["identityVerification"]["plainIdentityNo"] == "330101199001011234"
    assert result["identityVerification"]["plainCustomerName"] == "测试用户"
    assert result["identityVerification"]["plainMobile"] == "13800138000"
    assert result["identityVerification"]["smsCode"] == "123456"
    assert result["identityVerification"]["license"] == "LICENSE"
    assert result["identityVerification"]["verification"]["rawResponse"] == {"verified": True}
    assert result["agreementDocuments"][0]["contentBytes"] == 6


def test_product_workflow_can_omit_optional_identity_module(monkeypatch) -> None:
    _wire_fake_flows(monkeypatch)
    submission, snapshot = _prepared()
    snapshot = snapshot.model_copy(
        update={
            "workflow": (
                ProductWorkflowStep(id="application", module="application.apply", version=1),
            )
        }
    )
    calls: list[str] = []

    result = execute_product_application(
        runtime=FakePorts(calls),
        submission=submission,
        snapshot=snapshot,
        application_link_kind="internal",
    )

    assert calls == [
        "runtime.open",
        "application.execute",
        "runtime.close",
    ]
    assert result["identityVerificationCompleted"] is False
    assert result["identityVerification"] is None
    assert result["message"] == "申请链接、Session、协议及申请提交完成"


def test_product_workflow_rejects_missing_module_dependency_before_opening_runtime() -> None:
    submission, snapshot = _prepared()
    snapshot = snapshot.model_copy(
        update={
            "workflow": (
                ProductWorkflowStep(id="identity", module="identity.verify", version=1),
                ProductWorkflowStep(id="application", module="application.apply", version=1),
            )
        }
    )
    calls: list[str] = []

    with pytest.raises(ProductWorkflowConfigurationError, match="缺少前序输出"):
        execute_product_application(
            runtime=FakePorts(calls),
            submission=submission,
            snapshot=snapshot,
            application_link_kind="internal",
        )

    assert calls == []


def _identity_dependencies(monkeypatch, *, face_status="N", verification_success=True):
    monkeypatch.setattr(identity_module, "read_agreements", lambda **kwargs: {})
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
    identity_settings = config._mock_identity_settings()
    photo_client = None
    dcpp_client = None
    if sms_lookup is not None:
        identity_settings = identity_settings.model_copy(update={"mock": False})
        photo_client = type(
            "PhotoStub",
            (),
            {"delete_certificate_photo": lambda self, **kwargs: None},
        )()
        dcpp_client = type(
            "DcppStub",
            (),
            {"find_sms_code": staticmethod(sms_lookup)},
        )()
    return identity_module.execute_identity_verification(
        client=object(),
        settings=identity_settings,
        application_settings=config.get_cjdk_jyrc_settings(),
        payload=submission.payload,
        environment="UAT1",
        submission=SubmittedApplication(
            application_id="APPLY-1",
            encrypted_customer_name="ENC-NAME",
            encrypted_identity_no="ENC-ID",
        ),
        photo_client=photo_client,
        dcpp_client=dcpp_client,
        face_check_max_attempts=2,
    )


def test_identity_returns_complete_sensitive_result(monkeypatch) -> None:
    result = _execute_identity(monkeypatch)

    assert result["plain_identity_no"] == "330101199001011234"
    assert result["plain_customer_name"] == "测试用户"
    assert result["plain_mobile"] == "13800138000"
    assert result["encrypted_customer_name"] == "ENC-NAME"
    assert result["encrypted_identity_no"] == "ENC-ID"
    assert result["license"] == "LICENSE"
    assert result["sms_code"] == "123456"
    assert result["encrypted_sms_code"]
    assert result["verification"]["success"] is True


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
