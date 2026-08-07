from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class IdentityPublicKeyResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    public_key: str
    crypt_flow_no: str


class IdentityPrepareMobileResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    encrypted_mobile: str


class AliSdkParamsResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    trace_number: str
    license: str


class AliVideoCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: str | None = None
    message: str | None = None
    captcha_trace_id: str | None = None


class SmsSendResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    result_message: str | None = None
    pass_code_seq: str


class SmsCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    sms_message_id: str


class IdentityCardVerifyResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    success: bool = True
    message: str | None = None
    raw_response: dict[str, Any]


@dataclass
class IdentityContext:
    application_id: str
    product_id: str
    plain_identity_no: str
    plain_mobile: str
    encrypted_customer_name: str
    encrypted_identity_no: str
    branch_no: str
    card_no: str

    public_key: str | None = None
    crypt_flow_no: str | None = None
    encrypted_mobile: str | None = None
    trace_number: str | None = None
    license: str | None = None
    captcha_trace_id: str | None = None
    face_verify_message: str | None = None
    sms_code: str | None = None
    sms_message_id: str | None = None


@dataclass(frozen=True)
class IdentityVerificationOutcome:
    context: IdentityContext
    agreement_reading: Any
    verification: IdentityCardVerifyResult


class IdentityGateway(Protocol):
    def get_public_key(
        self, *, product_id: str, application_id: str
    ) -> IdentityPublicKeyResult: ...

    def get_prepare_mobile(
        self,
        *,
        encrypted_customer_name: str,
        encrypted_identity_no: str,
        branch_no: str,
        card_no: str,
    ) -> IdentityPrepareMobileResult: ...

    def get_ali_sdk_params(
        self, *, product_id: str, application_id: str
    ) -> AliSdkParamsResult: ...

    def ali_video_check(
        self,
        *,
        environment: str,
        product_id: str,
        application_id: str,
        encrypted_customer_name: str,
        encrypted_identity_no: str,
        encrypted_mobile: str,
        branch_no: str,
        trace_number: str,
        license: str,
    ) -> AliVideoCheckResult: ...

    def send_sms_code(
        self,
        *,
        product_id: str,
        branch_no: str,
        encrypted_mobile: str,
        captcha_trace_id: str,
    ) -> SmsSendResult: ...

    def check_sms_code(
        self,
        *,
        product_id: str,
        application_id: str,
        crypt_flow_no: str,
        encrypted_mobile: str,
        encrypted_sms_code: str,
        captcha_trace_id: str,
    ) -> SmsCheckResult: ...

    def verify_identity_card(self, *, context: IdentityContext) -> IdentityCardVerifyResult: ...


class PhotoGateway(Protocol):
    def delete_certificate_photo(self, *, identity_no: str) -> None: ...


class SmsCodeLookupGateway(Protocol):
    def find_sms_code(
        self,
        *,
        environment: str,
        mobile: str,
        pass_code_seq: str,
    ) -> str: ...
