import time
from collections.abc import Callable, Mapping
from typing import Any

from apps.utils.http.config import CjdkJyrcSettings, IdentitySettings
from apps.workflow.product_applications.cjdk.client import CjdkClient
from apps.workflow.product_applications.common.agreement import read_agreements
from apps.workflow.product_applications.contracts import SubmittedApplication
from apps.workflow.product_applications.identity.crypto import encrypt_sms_code
from apps.workflow.product_applications.identity.gateway import (
    ali_video_check,
    check_sms_code,
    get_ali_sdk_params,
    get_prepare_mobile,
    get_public_key,
    send_sms_code,
    verify_identity_card,
)


class IdentityFlowError(RuntimeError):
    pass


def execute_identity_verification(
    *,
    client: CjdkClient,
    settings: IdentitySettings,
    application_settings: CjdkJyrcSettings,
    payload: Mapping[str, Any],
    environment: str,
    submission: SubmittedApplication,
    photo_client: Any,
    dcpp_client: Any,
    progress: Callable[..., None] | None = None,
    face_check_max_attempts: int = 10,
    face_check_interval_seconds: float = 0,
) -> dict[str, Any]:
    product_id = _value(payload, "product")
    identity_no = _value(payload, "certificateNo")
    mobile = _value(payload, "phone", "mobile", "orgomalTel")
    person_name = _value(payload, "personName")
    branch_no = _value(payload, "branch")
    card_no = _value(payload, "cardNo")
    application_id = submission.application_id

    public_key, crypt_flow_no = get_public_key(
        client, settings, product_id=product_id, application_id=application_id
    )
    _report(progress, "identity_public_key", 91, "身份认证公钥获取完成")
    encrypted_mobile = get_prepare_mobile(
        client,
        settings,
        encrypted_customer_name=submission.encrypted_customer_name,
        encrypted_identity_no=submission.encrypted_identity_no,
        branch_no=branch_no,
        card_no=card_no,
    )
    _report(progress, "identity_mobile", 92, "加密手机号获取完成")
    read_agreements(
        client=client,
        settings=application_settings,
        payload=payload,
        scene="SC00016",
        stage_prefix="identity_agreement",
        progress_points=(93, 94, 95),
        progress=progress,
    )
    if not settings.mock:
        photo_client.delete_certificate_photo(identity_no=identity_no)
    _report(progress, "identity_photo_delete", 96, "历史人脸照片删除完成")
    trace_number, license = get_ali_sdk_params(
        client, settings, product_id=product_id, application_id=application_id
    )

    max_attempts = max(1, face_check_max_attempts)
    for face_attempts in range(1, max_attempts + 1):
        face_result = ali_video_check(
            client,
            settings,
            environment=environment,
            product_id=product_id,
            application_id=application_id,
            encrypted_customer_name=submission.encrypted_customer_name,
            encrypted_identity_no=submission.encrypted_identity_no,
            encrypted_mobile=encrypted_mobile,
            branch_no=branch_no,
            trace_number=trace_number,
            license=license,
        )
        if str(face_result.get("status") or "").upper() not in {"S", "E"}:
            break
        if face_attempts < max_attempts:
            time.sleep(max(0.0, face_check_interval_seconds))
    else:
        raise IdentityFlowError(f"人脸活检超过轮询上限：{max_attempts}")
    captcha_trace_id = str(face_result.get("captchaTraceId") or "")
    if not captcha_trace_id:
        raise IdentityFlowError("人脸活检未返回 captchTraceid/captchaTraceid")
    face_message = face_result.get("message")
    _report(progress, "identity_face_check", 97, "人脸活检完成")

    _, pass_code_seq = send_sms_code(
        client,
        settings,
        product_id=product_id,
        branch_no=branch_no,
        encrypted_mobile=encrypted_mobile,
        captcha_trace_id=captcha_trace_id,
    )
    sms_code = (
        "123456"
        if settings.mock
        else dcpp_client.find_sms_code(
            environment=environment,
            mobile=mobile,
            pass_code_seq=pass_code_seq,
        )
    )
    encrypted_sms_code = encrypt_sms_code(public_key=public_key, sms_code=sms_code)
    sms_message_id = check_sms_code(
        client,
        settings,
        product_id=product_id,
        application_id=application_id,
        crypt_flow_no=crypt_flow_no,
        encrypted_mobile=encrypted_mobile,
        encrypted_sms_code=encrypted_sms_code,
        captcha_trace_id=captcha_trace_id,
    )
    _report(progress, "identity_sms_check", 98, "短信验证码校验完成")
    verification = verify_identity_card(
        client,
        settings,
        product_id=product_id,
        application_id=application_id,
        encrypted_customer_name=submission.encrypted_customer_name,
        encrypted_identity_no=submission.encrypted_identity_no,
        encrypted_mobile=encrypted_mobile,
        captcha_trace_id=captcha_trace_id,
        sms_message_id=sms_message_id,
        crypt_flow_no=crypt_flow_no,
    )
    if not verification.get("success"):
        raise IdentityFlowError(str(verification.get("message") or "身份验证失败"))
    _report(progress, "identity_verify", 99, "身份验证完成")

    return {
        "application_id": application_id,
        "product_id": product_id,
        "plain_customer_name": person_name,
        "plain_identity_no": identity_no,
        "plain_mobile": mobile,
        "encrypted_customer_name": submission.encrypted_customer_name,
        "encrypted_identity_no": submission.encrypted_identity_no,
        "branch_no": branch_no,
        "card_no": card_no,
        "public_key": public_key,
        "crypt_flow_no": crypt_flow_no,
        "encrypted_mobile": encrypted_mobile,
        "trace_number": trace_number,
        "license": license,
        "captcha_trace_id": captcha_trace_id,
        "face_verify_status": str(face_result.get("status") or ""),
        "face_verify_message": face_message,
        "face_check_attempts": face_attempts,
        "pass_code_seq": pass_code_seq,
        "sms_code": sms_code,
        "encrypted_sms_code": encrypted_sms_code,
        "sms_message_id": sms_message_id,
        "verification": verification,
    }


def _value(payload: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        if value := str(payload.get(key) or "").strip():
            return value
    raise IdentityFlowError(f"缺少身份认证字段：{'/'.join(keys)}")


def _report(callback: Callable[..., None] | None, stage: str, progress: int, message: str) -> None:
    if callback:
        callback(stage=stage, progress=progress, message=message)
