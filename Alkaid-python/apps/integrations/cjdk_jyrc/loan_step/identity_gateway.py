from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.integrations.cjdk_jyrc.client import CjdkJyrcClient
from apps.integrations.cjdk_jyrc.loan_step.identity_api import (
    ali_video_check_endpoint,
    get_ali_sdk_params_endpoint,
    get_prepare_mobile_endpoint,
    get_public_key_endpoint,
    identity_card_verify_endpoint,
    sms_code_check_endpoint,
    sms_code_send_endpoint,
)
from apps.integrations.cjdk_jyrc.loan_step.identity_config import IdentitySettings
from apps.integrations.cjdk_jyrc.messages import new_message
from apps.product_data.product_applications.common.values import (
    required_response_text,
)
from apps.product_data.product_applications.loan_step.identity_contracts import (
    AliSdkParamsResult,
    AliVideoCheckResult,
    IdentityCardVerifyResult,
    IdentityContext,
    IdentityPrepareMobileResult,
    IdentityPublicKeyResult,
    SmsCheckResult,
    SmsSendResult,
)


class IdentityProtocolError(RuntimeError):
    pass


class CjdkIdentityGateway:
    def __init__(
        self,
        *,
        client: CjdkJyrcClient,
        settings: IdentitySettings,
    ) -> None:
        self._client = client
        self._settings = settings

    def get_public_key(
        self,
        *,
        product_id: str,
        application_id: str,
    ) -> IdentityPublicKeyResult:
        message = new_message("identity_get_public_key_v1")
        request = _request(message)
        request.update(
            {
                "selblProdId": product_id,
                "businessNo": application_id,
            }
        )
        response = self._client.request(
            step="identity.get_public_key",
            endpoint=get_public_key_endpoint(self._settings),
            message=message,
        )
        data = response.rsp_body.response
        return IdentityPublicKeyResult(
            public_key=required_response_text(data, "pubKey", label="pubKey"),
            crypt_flow_no=required_response_text(
                data, "cryptFlowNo", label="cryptFlowNo"
            ),
        )

    def get_prepare_mobile(
        self,
        *,
        encrypted_customer_name: str,
        encrypted_identity_no: str,
        branch_no: str,
        card_no: str,
    ) -> IdentityPrepareMobileResult:
        message = new_message("identity_get_prepare_mobile_v1")
        request = _request(message)
        request.update(
            {
                "custName": encrypted_customer_name,
                "identityNo": encrypted_identity_no,
                "branchNo": branch_no,
                "cardNo": card_no,
            }
        )
        response = self._client.request(
            step="identity.get_prepare_mobile",
            endpoint=get_prepare_mobile_endpoint(self._settings),
            message=message,
        )
        data = response.rsp_body.response
        return IdentityPrepareMobileResult(
            encrypted_mobile=required_response_text(data, "mobile", label="mobile")
        )

    def get_ali_sdk_params(
        self,
        *,
        product_id: str,
        application_id: str,
    ) -> AliSdkParamsResult:
        message = new_message("identity_ali_sdk_params_v1")
        request = _request(message)
        request.update(
            {
                "traceNumber": application_id,
                "selblProdId": product_id,
                "applyNo": application_id,
            }
        )
        response = self._client.request(
            step="identity.ali_sdk_params",
            endpoint=get_ali_sdk_params_endpoint(self._settings),
            message=message,
        )
        data = response.rsp_body.response
        return AliSdkParamsResult(
            trace_number=required_response_text(
                data, "traceNumber", label="traceNumber"
            ),
            license=required_response_text(data, "license", label="license"),
        )

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
    ) -> AliVideoCheckResult:
        message = new_message(self._settings.video_message_name(environment))
        request = _request(message)
        request.update(
            {
                "selblProdId": product_id,
                "idNo": encrypted_identity_no,
                "idName": encrypted_customer_name,
                "traceNumber": trace_number,
                "branchNo": branch_no,
                "bizId": application_id,
                "license": license,
                "applyNo": application_id,
                "mobile": encrypted_mobile,
            }
        )
        response = self._client.request(
            step="identity.ali_video_check",
            endpoint=ali_video_check_endpoint(self._settings),
            message=message,
        )
        data = response.rsp_body.response
        status = _first_text(
            response.rsp_head,
            "PROCESS_STATUS_CODE",
            "processStatusCode",
        )
        return AliVideoCheckResult(
            status=status,
            message=_first_text(
                data,
                "verifyResultDtlMessage",
                "dataMessage",
                "message",
            ),
            captcha_trace_id=_first_text(
                data,
                "captchTraceid",
                "captchaTraceid",
                "captchaTraceId",
            ),
        )

    def send_sms_code(
        self,
        *,
        product_id: str,
        branch_no: str,
        encrypted_mobile: str,
        captcha_trace_id: str,
    ) -> SmsSendResult:
        message = new_message("identity_sms_code_send_v1")
        request = _request(message)
        request.update(
            {
                "mobile": encrypted_mobile,
                "branchNo": branch_no,
                "selblProdId": product_id,
                "captchTraceid": captcha_trace_id,
            }
        )
        response = self._client.request(
            step="identity.sms_code_send",
            endpoint=sms_code_send_endpoint(self._settings),
            message=message,
        )
        data = response.rsp_body.response
        pass_code_seq = required_response_text(
            data,
            "passCodeSeq",
            "passcodeSeq",
            label="passCodeSeq",
        )
        return SmsSendResult(
            result_message=_first_text(data, "resultMessage", "message"),
            pass_code_seq=pass_code_seq,
        )

    def check_sms_code(
        self,
        *,
        product_id: str,
        application_id: str,
        crypt_flow_no: str,
        encrypted_mobile: str,
        encrypted_sms_code: str,
        captcha_trace_id: str,
    ) -> SmsCheckResult:
        message = new_message("identity_sms_code_check_v1")
        request = _request(message)
        request.update(
            {
                "cryptFlowNo": crypt_flow_no,
                "mobile": encrypted_mobile,
                "mobileCode": encrypted_sms_code,
                "captchTraceid": captcha_trace_id,
                "selblProdId": product_id,
                "businessNo": application_id,
            }
        )
        response = self._client.request(
            step="identity.sms_code_check",
            endpoint=sms_code_check_endpoint(self._settings),
            message=message,
        )
        data = response.rsp_body.response
        return SmsCheckResult(
            sms_message_id=required_response_text(
                data, "smsMessageId", label="smsMessageId"
            )
        )

    def verify_identity_card(
        self,
        *,
        context: IdentityContext,
    ) -> IdentityCardVerifyResult:
        message = new_message("identity_card_verify_v1")
        request = _request(message)

        # identityCardVerify 的完整报文未提供，因此这里采用“模板决定字段、代码只填动态值”。
        # 你把旧项目真实 raw message 放入 loanIdentity.json 后，这里无需再改结构。
        dynamic_values: dict[str, str] = {
            "selblProdId": context.product_id,
            "businessNo": context.application_id,
            "applyNo": context.application_id,
            "custName": context.encrypted_customer_name,
            "identityNo": context.encrypted_identity_no,
            "idNo": context.encrypted_identity_no,
            "mobile": context.encrypted_mobile or "",
            "captchTraceid": context.captcha_trace_id or "",
            "captchaTraceid": context.captcha_trace_id or "",
            "smsMessageId": context.sms_message_id or "",
            "cryptFlowNo": context.crypt_flow_no or "",
        }
        for key, value in dynamic_values.items():
            if key in request:
                request[key] = value

        response = self._client.request(
            step="identity.card_verify",
            endpoint=identity_card_verify_endpoint(self._settings),
            message=message,
        )
        data = response.rsp_body.response
        return IdentityCardVerifyResult(
            success=True,
            message=_first_text(data, "resultMessage", "message", "promptInf"),
            raw_response=dict(data),
        )


def _request(message: dict[str, Any]) -> dict[str, Any]:
    try:
        request = message["REQ_BODY"]["request"]
    except (KeyError, TypeError) as exc:
        raise IdentityProtocolError("身份认证原始报文缺少 REQ_BODY.request") from exc
    if not isinstance(request, dict):
        raise IdentityProtocolError("身份认证 REQ_BODY.request 必须是 JSON 对象")
    return request


def _first_text(source: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None
