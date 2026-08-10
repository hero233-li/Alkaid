import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.utils.http.config import IdentitySettings
from apps.utils.http.contracts import EndpointSpec, RetryMode
from apps.workflow.product_applications.cjdk.client import CjdkClient

MESSAGE_FILE = Path(__file__).parents[3] / "config" / "raw_messages" / "loanIdentity.json"
REQUIRED_MESSAGES = {
    "identity_get_public_key_v1",
    "identity_get_prepare_mobile_v1",
    "identity_ali_sdk_params_v1",
    "identity_ali_video_check_u12_v1",
    "identity_ali_video_check_uc_v1",
    "identity_sms_code_send_v1",
    "identity_sms_code_check_v1",
    "identity_card_verify_v1",
}


class IdentityResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    rsp_body: dict[str, Any] = Field(alias="RSP_BODY")
    rsp_head: dict[str, Any] = Field(default_factory=dict, alias="RSP_HEAD")


def new_message(name: str) -> dict[str, Any]:
    return json.loads(MESSAGE_FILE.read_text(encoding="utf-8"))[name]


def validate_identity_messages() -> dict[str, int]:
    messages = json.loads(MESSAGE_FILE.read_text(encoding="utf-8"))
    missing = REQUIRED_MESSAGES - messages.keys()
    if missing:
        raise ValueError(f"缺少身份认证原始报文：{', '.join(sorted(missing))}")
    return {"messages": len(messages)}


def _endpoint(operation_id: str, path: str) -> EndpointSpec[IdentityResponse]:
    path = path if path.startswith("/") else f"/{path}"
    return EndpointSpec(
        operation_id=operation_id,
        method="POST",
        path=path,
        response_model=IdentityResponse,
        retry_mode=RetryMode.NEVER,
    )


def _call(
    client: CjdkClient,
    settings: IdentitySettings,
    *,
    step: str,
    operation_id: str,
    endpoint_name: str,
    message_name: str,
    values: Mapping[str, Any],
) -> IdentityResponse:
    message = new_message(message_name)
    message["REQ_BODY"]["request"].update(values)
    return client.request(
        step=step,
        endpoint=_endpoint(operation_id, settings.endpoint(endpoint_name)),
        message=message,
    )


def _text(source: Mapping[str, Any], *keys: str, required: bool = True) -> str | None:
    for key in keys:
        if value := str(source.get(key) or "").strip():
            return value
    if required:
        raise RuntimeError(f"外系统响应缺少字段：{'/'.join(keys)}")
    return None


def get_public_key(
    client: CjdkClient, settings: IdentitySettings, *, product_id: str, application_id: str
) -> tuple[str, str]:
    response = _call(
        client,
        settings,
        step="identity.get_public_key",
        operation_id="cjdk_jyrc.identity_get_public_key",
        endpoint_name="getPublicKey",
        message_name="identity_get_public_key_v1",
        values={"selblProdId": product_id, "businessNo": application_id},
    )
    data = response.rsp_body["response"]
    return _text(data, "pubKey"), _text(data, "cryptFlowNo")


def get_prepare_mobile(
    client: CjdkClient,
    settings: IdentitySettings,
    *,
    encrypted_customer_name: str,
    encrypted_identity_no: str,
    branch_no: str,
    card_no: str,
) -> str:
    response = _call(
        client,
        settings,
        step="identity.get_prepare_mobile",
        operation_id="cjdk_jyrc.identity_get_prepare_mobile",
        endpoint_name="getPrepareMobile",
        message_name="identity_get_prepare_mobile_v1",
        values={
            "custName": encrypted_customer_name,
            "identityNo": encrypted_identity_no,
            "branchNo": branch_no,
            "cardNo": card_no,
        },
    )
    return _text(response.rsp_body["response"], "mobile")


def get_ali_sdk_params(
    client: CjdkClient, settings: IdentitySettings, *, product_id: str, application_id: str
) -> tuple[str, str]:
    response = _call(
        client,
        settings,
        step="identity.ali_sdk_params",
        operation_id="cjdk_jyrc.identity_get_ali_sdk_params",
        endpoint_name="getAliSdkParams",
        message_name="identity_ali_sdk_params_v1",
        values={
            "traceNumber": application_id,
            "selblProdId": product_id,
            "applyNo": application_id,
        },
    )
    data = response.rsp_body["response"]
    return _text(data, "traceNumber"), _text(data, "license")


def ali_video_check(
    client: CjdkClient,
    settings: IdentitySettings,
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
) -> dict[str, Any]:
    response = _call(
        client,
        settings,
        step="identity.ali_video_check",
        operation_id="cjdk_jyrc.identity_ali_video_check",
        endpoint_name="aliVideoCheck",
        message_name=settings.video_message_name(environment),
        values={
            "selblProdId": product_id,
            "idNo": encrypted_identity_no,
            "idName": encrypted_customer_name,
            "traceNumber": trace_number,
            "branchNo": branch_no,
            "bizId": application_id,
            "license": license,
            "applyNo": application_id,
            "mobile": encrypted_mobile,
        },
    )
    data = response.rsp_body["response"]
    return {
        "status": _text(
            response.rsp_head, "PROCESS_STATUS_CODE", "processStatusCode", required=False
        ),
        "message": _text(data, "verifyResultDtlMessage", "dataMessage", "message", required=False),
        "captchaTraceId": _text(
            data, "captchTraceid", "captchaTraceid", "captchaTraceId", required=False
        ),
    }


def send_sms_code(
    client: CjdkClient,
    settings: IdentitySettings,
    *,
    product_id: str,
    branch_no: str,
    encrypted_mobile: str,
    captcha_trace_id: str,
) -> tuple[str | None, str]:
    response = _call(
        client,
        settings,
        step="identity.sms_code_send",
        operation_id="cjdk_jyrc.identity_sms_code_send",
        endpoint_name="smsCodeSend",
        message_name="identity_sms_code_send_v1",
        values={
            "mobile": encrypted_mobile,
            "branchNo": branch_no,
            "selblProdId": product_id,
            "captchTraceid": captcha_trace_id,
        },
    )
    data = response.rsp_body["response"]
    return _text(data, "resultMessage", "message", required=False), _text(
        data, "passCodeSeq", "passcodeSeq"
    )


def check_sms_code(
    client: CjdkClient,
    settings: IdentitySettings,
    *,
    product_id: str,
    application_id: str,
    crypt_flow_no: str,
    encrypted_mobile: str,
    encrypted_sms_code: str,
    captcha_trace_id: str,
) -> str:
    response = _call(
        client,
        settings,
        step="identity.sms_code_check",
        operation_id="cjdk_jyrc.identity_sms_code_check",
        endpoint_name="smsCodeCheck",
        message_name="identity_sms_code_check_v1",
        values={
            "cryptFlowNo": crypt_flow_no,
            "mobile": encrypted_mobile,
            "mobileCode": encrypted_sms_code,
            "captchTraceid": captcha_trace_id,
            "selblProdId": product_id,
            "businessNo": application_id,
        },
    )
    return _text(response.rsp_body["response"], "smsMessageId")


def verify_identity_card(
    client: CjdkClient,
    settings: IdentitySettings,
    *,
    product_id: str,
    application_id: str,
    encrypted_customer_name: str,
    encrypted_identity_no: str,
    encrypted_mobile: str,
    captcha_trace_id: str,
    sms_message_id: str,
    crypt_flow_no: str,
) -> dict[str, Any]:
    message = new_message("identity_card_verify_v1")
    request = message["REQ_BODY"]["request"]
    values = {
        "selblProdId": product_id,
        "businessNo": application_id,
        "applyNo": application_id,
        "custName": encrypted_customer_name,
        "identityNo": encrypted_identity_no,
        "idNo": encrypted_identity_no,
        "mobile": encrypted_mobile,
        "captchTraceid": captcha_trace_id,
        "captchaTraceid": captcha_trace_id,
        "smsMessageId": sms_message_id,
        "cryptFlowNo": crypt_flow_no,
    }
    request.update({key: value for key, value in values.items() if key in request})
    response = client.request(
        step="identity.card_verify",
        endpoint=_endpoint(
            "cjdk_jyrc.identity_card_verify", settings.endpoint("identityCardVerify")
        ),
        message=message,
    )
    data = response.rsp_body["response"]
    return {
        "success": True,
        "message": _text(data, "resultMessage", "message", "promptInf", required=False),
        "rawResponse": data,
    }
