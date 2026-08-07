from __future__ import annotations

from apps.integrations.cjdk_jyrc.loan_step.identity_config import IdentitySettings
from apps.integrations.cjdk_jyrc.loan_step.identity_models import GenericIdentityEnvelope
from apps.integrations.contracts import EndpointSpec, RetryMode


def _endpoint(operation_id: str, path: str) -> EndpointSpec[GenericIdentityEnvelope]:
    normalized = path.strip()
    if not normalized or "REPLACE" in normalized.upper() or "TODO" in normalized.upper():
        raise RuntimeError(f"身份认证接口 path 尚未配置：{operation_id} -> {path!r}")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return EndpointSpec(
        operation_id=operation_id,
        method="POST",
        path=normalized,
        response_model=GenericIdentityEnvelope,
        retry_mode=RetryMode.NEVER,
    )


def get_public_key_endpoint(settings: IdentitySettings) -> EndpointSpec[GenericIdentityEnvelope]:
    return _endpoint("cjdk_jyrc.identity_get_public_key", settings.endpoints.get_public_key)


def get_prepare_mobile_endpoint(settings: IdentitySettings) -> EndpointSpec[GenericIdentityEnvelope]:
    return _endpoint(
        "cjdk_jyrc.identity_get_prepare_mobile",
        settings.endpoints.get_prepare_mobile,
    )


def get_ali_sdk_params_endpoint(settings: IdentitySettings) -> EndpointSpec[GenericIdentityEnvelope]:
    return _endpoint(
        "cjdk_jyrc.identity_get_ali_sdk_params",
        settings.endpoints.get_ali_sdk_params,
    )


def ali_video_check_endpoint(settings: IdentitySettings) -> EndpointSpec[GenericIdentityEnvelope]:
    return _endpoint(
        "cjdk_jyrc.identity_ali_video_check",
        settings.endpoints.ali_video_check,
    )


def sms_code_send_endpoint(settings: IdentitySettings) -> EndpointSpec[GenericIdentityEnvelope]:
    return _endpoint(
        "cjdk_jyrc.identity_sms_code_send",
        settings.endpoints.sms_code_send,
    )


def sms_code_check_endpoint(settings: IdentitySettings) -> EndpointSpec[GenericIdentityEnvelope]:
    return _endpoint(
        "cjdk_jyrc.identity_sms_code_check",
        settings.endpoints.sms_code_check,
    )


def identity_card_verify_endpoint(settings: IdentitySettings) -> EndpointSpec[GenericIdentityEnvelope]:
    return _endpoint(
        "cjdk_jyrc.identity_card_verify",
        settings.endpoints.identity_card_verify,
    )
