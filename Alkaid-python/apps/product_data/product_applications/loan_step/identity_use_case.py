from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from apps.product_data.product_applications.agreement_use_case import (
    query_preview_and_read_agreements,
)
from apps.product_data.product_applications.common.values import (
    required_first_text,
    required_text,
)
from apps.product_data.product_applications.contracts import (
    AgreementGateway,
    ExternalSessionGateway,
    ProgressReporter,
)
from apps.product_data.product_applications.loan_step.identity_contracts import (
    IdentityContext,
    IdentityGateway,
    IdentityVerificationOutcome,
    PhotoGateway,
    SmsCodeLookupGateway,
)
from apps.integrations.cjdk_jyrc.loan_step.crypto import encrypt_sms_code


class IdentityVerificationError(RuntimeError):
    pass


def execute_identity_verification(
    *,
    identities: IdentityGateway,
    photos: PhotoGateway,
    sms_lookup: SmsCodeLookupGateway,
    agreements: AgreementGateway,
    external_session: ExternalSessionGateway,
    payload: Mapping[str, Any],
    environment: str,
    application_id: str,
    encrypted_customer_name: str,
    encrypted_identity_no: str,
    progress: ProgressReporter | None = None,
    face_check_max_attempts: int = 10,
    face_check_interval_seconds: float = 1.0,
) -> IdentityVerificationOutcome:
    context = IdentityContext(
        application_id=application_id,
        product_id=required_text(payload, "product", "产品编号"),
        plain_identity_no=required_text(payload, "certificateNo", "证件号码"),
        plain_mobile=required_first_text(
            payload,
            ("phone", "mobile", "orgomalTel"),
            "手机号",
        ),
        encrypted_customer_name=encrypted_customer_name,
        encrypted_identity_no=encrypted_identity_no,
        branch_no=required_text(payload, "branch", "辖行编号"),
        card_no=required_text(payload, "cardNo", "卡号"),
    )

    pub_key_result = identities.get_public_key(
        product_id=context.product_id,
        application_id=context.application_id,
    )
    context.public_key = pub_key_result.public_key
    context.crypt_flow_no = pub_key_result.crypt_flow_no
    _report(progress, "identity_public_key", 91, "身份认证公钥获取完成")

    mobile_result = identities.get_prepare_mobile(
        encrypted_customer_name=context.encrypted_customer_name,
        encrypted_identity_no=context.encrypted_identity_no,
        branch_no=context.branch_no,
        card_no=context.card_no,
    )
    context.encrypted_mobile = mobile_result.encrypted_mobile
    _report(progress, "identity_mobile", 92, "加密手机号获取完成")

    agreement_reading = query_preview_and_read_agreements(
        agreements=agreements,
        external_session=external_session,
        payload=payload,
        scene="SC00016",
        stage_prefix="identity_agreement",
        progress_points=(93, 94, 95),
        progress=progress,
    )

    photos.delete_certificate_photo(identity_no=context.plain_identity_no)
    _report(progress, "identity_photo_delete", 96, "历史人脸照片删除完成")

    sdk_result = identities.get_ali_sdk_params(
        product_id=context.product_id,
        application_id=context.application_id,
    )
    context.trace_number = sdk_result.trace_number
    context.license = sdk_result.license

    face_result = None
    for attempt in range(1, max(1, face_check_max_attempts) + 1):
        face_result = identities.ali_video_check(
            environment=environment,
            product_id=context.product_id,
            application_id=context.application_id,
            encrypted_customer_name=context.encrypted_customer_name,
            encrypted_identity_no=context.encrypted_identity_no,
            encrypted_mobile=_required_context(context.encrypted_mobile, "encrypted_mobile"),
            branch_no=context.branch_no,
            trace_number=_required_context(context.trace_number, "trace_number"),
            license=_required_context(context.license, "license"),
        )
        context.face_verify_message = face_result.message
        if face_result.captcha_trace_id:
            context.captcha_trace_id = face_result.captcha_trace_id

        # 保留旧流程语义：S/E 时继续查询，但禁止无限循环。
        if (face_result.status or "").upper() not in {"S", "E"}:
            break
        if attempt < face_check_max_attempts:
            time.sleep(max(0.0, face_check_interval_seconds))

    if face_result is None:
        raise IdentityVerificationError("人脸活检未执行")
    if not context.captcha_trace_id:
        raise IdentityVerificationError(
            f"人脸活检未返回 captchTraceid/captchaTraceid，status={face_result.status!r}"
        )
    _report(progress, "identity_face_check", 97, "人脸活检完成")

    sms_send = identities.send_sms_code(
        product_id=context.product_id,
        branch_no=context.branch_no,
        encrypted_mobile=_required_context(context.encrypted_mobile, "encrypted_mobile"),
        captcha_trace_id=_required_context(context.captcha_trace_id, "captcha_trace_id"),
    )

    sms_code = sms_lookup.find_sms_code(
        environment=environment,
        mobile=context.plain_mobile,
        pass_code_seq=sms_send.pass_code_seq,
    )
    context.sms_code = sms_code

    encrypted_sms_code = encrypt_sms_code(
        public_key=_required_context(context.public_key, "public_key"),
        sms_code=sms_code,
    )

    sms_check = identities.check_sms_code(
        product_id=context.product_id,
        application_id=context.application_id,
        crypt_flow_no=_required_context(context.crypt_flow_no, "crypt_flow_no"),
        encrypted_mobile=_required_context(context.encrypted_mobile, "encrypted_mobile"),
        encrypted_sms_code=encrypted_sms_code,
        captcha_trace_id=_required_context(context.captcha_trace_id, "captcha_trace_id"),
    )
    context.sms_message_id = sms_check.sms_message_id
    _report(progress, "identity_sms_check", 98, "短信验证码校验完成")

    verification = identities.verify_identity_card(context=context)
    _report(progress, "identity_verify", 99, "身份验证完成")

    return IdentityVerificationOutcome(
        context=context,
        agreement_reading=agreement_reading,
        verification=verification,
    )


def _required_context(value: str | None, name: str) -> str:
    if value is None or not str(value).strip():
        raise IdentityVerificationError(f"身份认证上下文缺少字段：{name}")
    return str(value).strip()


def _report(
    reporter: ProgressReporter | None,
    stage: str,
    progress: int,
    message: str,
) -> None:
    if reporter is not None:
        reporter(stage=stage, progress=progress, message=message)
