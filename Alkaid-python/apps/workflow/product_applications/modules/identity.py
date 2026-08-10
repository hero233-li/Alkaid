from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from apps.workflow.product_applications.cjdk.runtime import ProductApplicationRuntime
from apps.workflow.product_applications.contracts import SubmittedApplication
from apps.workflow.product_applications.identity.identity import execute_identity_verification


@dataclass(frozen=True, slots=True)
class IdentityModuleOutcome:
    completed: bool
    application_id: str
    product_id: str
    plain_customer_name: str
    plain_identity_no: str
    plain_mobile: str
    encrypted_customer_name: str
    encrypted_identity_no: str
    branch_no: str
    card_no: str
    public_key: str
    crypt_flow_no: str
    encrypted_mobile: str
    trace_number: str
    license: str
    captcha_trace_id: str
    face_verify_status: str
    face_verify_message: str | None
    face_check_attempts: int
    pass_code_seq: str
    sms_code: str
    encrypted_sms_code: str
    sms_message_id: str
    verification: dict[str, Any]

    def as_api_result(self) -> dict[str, Any]:
        return {
            "completed": self.completed,
            "applicationId": self.application_id,
            "productId": self.product_id,
            "plainCustomerName": self.plain_customer_name,
            "plainIdentityNo": self.plain_identity_no,
            "plainMobile": self.plain_mobile,
            "encryptedCustomerName": self.encrypted_customer_name,
            "encryptedIdentityNo": self.encrypted_identity_no,
            "branchNo": self.branch_no,
            "cardNo": self.card_no,
            "publicKey": self.public_key,
            "cryptFlowNo": self.crypt_flow_no,
            "encryptedMobile": self.encrypted_mobile,
            "traceNumber": self.trace_number,
            "license": self.license,
            "captchaTraceId": self.captcha_trace_id,
            "faceVerifyStatus": self.face_verify_status,
            "faceVerifyMessage": self.face_verify_message,
            "faceCheckAttempts": self.face_check_attempts,
            "passCodeSeq": self.pass_code_seq,
            "smsCode": self.sms_code,
            "encryptedSmsCode": self.encrypted_sms_code,
            "smsMessageId": self.sms_message_id,
            "verification": self.verification,
        }


def execute_identity_module(
    *,
    runtime: ProductApplicationRuntime,
    payload: Mapping[str, Any],
    environment: str,
    submitted_application: SubmittedApplication,
    progress: Callable[..., None] | None = None,
) -> IdentityModuleOutcome:
    result = execute_identity_verification(
        client=runtime.client,
        settings=runtime.identity_settings,
        application_settings=runtime.settings,
        payload=payload,
        environment=environment,
        submission=submitted_application,
        photo_client=runtime.photo_client,
        dcpp_client=runtime.dcpp_client,
        progress=progress,
    )
    return IdentityModuleOutcome(completed=True, **result)
