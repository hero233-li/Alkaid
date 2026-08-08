from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from apps.integrations.contracts import EndpointSpec, RetryMode
from apps.product_applications.cjdk.config import (
    DcppEnvironmentSettings,
    IdentitySettings,
    PhotoEnvironmentSettings,
)
from apps.product_applications.cjdk.runtime import CjdkClient, CjdkEnvelope, new_message

ApplicationSubmission = tuple[str, str, str]
ProgressReporter = Callable[..., None]


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


class IdentityFlowError(RuntimeError):
    pass


def execute_identity_verification(
    *,
    client: CjdkClient,
    settings: IdentitySettings,
    payload: Mapping[str, Any],
    environment: str,
    submission: ApplicationSubmission,
    read_agreements: Callable[..., dict[str, Any]],
    delete_photo: Callable[..., None],
    find_sms_code: Callable[..., str],
    progress: ProgressReporter | None = None,
    face_check_max_attempts: int = 10,
    face_check_interval_seconds: float = 0,
) -> None:
    context = IdentityContext(
        application_id=submission[0],
        product_id=_required_payload(payload, "product", "产品编号"),
        plain_identity_no=_required_payload(payload, "certificateNo", "证件号码"),
        plain_mobile=_required_first(payload, ("phone", "mobile", "orgomalTel"), "手机号"),
        encrypted_customer_name=submission[1],
        encrypted_identity_no=submission[2],
        branch_no=_required_payload(payload, "branch", "辖行编号"),
        card_no=_required_payload(payload, "cardNo", "卡号"),
    )
    context.public_key, context.crypt_flow_no = get_public_key(
        client,
        settings,
        product_id=context.product_id,
        application_id=context.application_id,
    )
    _report(progress, "identity_public_key", 91, "身份认证公钥获取完成")
    context.encrypted_mobile = get_prepare_mobile(
        client,
        settings,
        encrypted_customer_name=context.encrypted_customer_name,
        encrypted_identity_no=context.encrypted_identity_no,
        branch_no=context.branch_no,
        card_no=context.card_no,
    )
    _report(progress, "identity_mobile", 92, "加密手机号获取完成")
    read_agreements(
        payload=payload,
        scene="SC00016",
        stage_prefix="identity_agreement",
        progress_points=(93, 94, 95),
        progress=progress,
    )
    delete_photo(identity_no=context.plain_identity_no)
    _report(progress, "identity_photo_delete", 96, "历史人脸照片删除完成")
    context.trace_number, context.license = get_ali_sdk_params(
        client,
        settings,
        product_id=context.product_id,
        application_id=context.application_id,
    )
    face_result: dict[str, Any] | None = None
    max_attempts = max(1, face_check_max_attempts)
    for attempt in range(1, max_attempts + 1):
        face_result = ali_video_check(
            client,
            settings,
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
        context.face_verify_message = _first_text(face_result, "message")
        if face_result.get("captchaTraceId"):
            context.captcha_trace_id = str(face_result["captchaTraceId"])
        if str(face_result.get("status") or "").upper() not in {"S", "E"}:
            break
        if attempt < max_attempts:
            time.sleep(max(0.0, face_check_interval_seconds))
    if face_result is None:
        raise IdentityFlowError("人脸活检未执行")
    if str(face_result.get("status") or "").upper() in {"S", "E"}:
        raise IdentityFlowError(f"人脸活检超过轮询上限：{max_attempts}")
    if not context.captcha_trace_id:
        raise IdentityFlowError(
            f"人脸活检未返回 captchTraceid/captchaTraceid，status={face_result.get('status')!r}"
        )
    _report(progress, "identity_face_check", 97, "人脸活检完成")
    _, pass_code_seq = send_sms_code(
        client,
        settings,
        product_id=context.product_id,
        branch_no=context.branch_no,
        encrypted_mobile=_required_context(context.encrypted_mobile, "encrypted_mobile"),
        captcha_trace_id=_required_context(context.captcha_trace_id, "captcha_trace_id"),
    )
    context.sms_code = find_sms_code(
        environment=environment,
        mobile=context.plain_mobile,
        pass_code_seq=pass_code_seq,
    )
    encrypted_sms_code = encrypt_sms_code(
        public_key=_required_context(context.public_key, "public_key"),
        sms_code=context.sms_code,
    )
    context.sms_message_id = check_sms_code(
        client,
        settings,
        product_id=context.product_id,
        application_id=context.application_id,
        crypt_flow_no=_required_context(context.crypt_flow_no, "crypt_flow_no"),
        encrypted_mobile=_required_context(context.encrypted_mobile, "encrypted_mobile"),
        encrypted_sms_code=encrypted_sms_code,
        captcha_trace_id=_required_context(context.captcha_trace_id, "captcha_trace_id"),
    )
    _report(progress, "identity_sms_check", 98, "短信验证码校验完成")
    verification = verify_identity_card(client, settings, context=context)
    if not verification.get("success"):
        raise IdentityFlowError(str(verification.get("message") or "身份验证失败"))
    _report(progress, "identity_verify", 99, "身份验证完成")


def _required_payload(source: Mapping[str, Any], key: str, label: str) -> str:
    value = source.get(key)
    normalized = str(value).strip() if value is not None else ""
    if not normalized:
        raise IdentityFlowError(f"缺少{label}：{key}")
    return normalized


def _required_first(source: Mapping[str, Any], keys: tuple[str, ...], label: str) -> str:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    raise IdentityFlowError(f"缺少{label}：候选字段={', '.join(keys)}")


def _required_context(value: str | None, name: str) -> str:
    if value is None or not str(value).strip():
        raise IdentityFlowError(f"身份认证上下文缺少字段：{name}")
    return str(value).strip()


def _report(reporter: ProgressReporter | None, stage: str, progress: int, message: str) -> None:
    if reporter is not None:
        reporter(stage=stage, progress=progress, message=message)


def normalize_sm2_public_key(public_key: str) -> str:
    normalized = public_key.strip()
    if not normalized:
        raise IdentityFlowError("SM2 public_key 为空")
    return normalized if normalized.startswith("04") else f"04{normalized}"


def encrypt_sms_code(*, public_key: str, sms_code: str) -> str:
    code = sms_code.strip()
    if not code:
        raise IdentityFlowError("短信验证码为空")
    if public_key.startswith("MOCK-"):
        return hashlib.sha256(f"{public_key}:{code}".encode()).hexdigest()
    try:
        from jyd_loan.utils.message import sm2
    except ImportError as exc:
        raise IdentityFlowError(
            "当前环境未安装旧项目使用的 jyd_loan.utils.message.sm2；"
            "请把内网已有 SM2 实现接到 CJDK identity 模块"
        ) from exc
    normalized_key = normalize_sm2_public_key(public_key)
    try:
        crypt_sm2 = sm2.CryptSM2(None, normalized_key, mode=1)
        return crypt_sm2.encrypt(code.encode()).hex()
    except Exception as exc:
        raise IdentityFlowError(f"SM2 加密短信验证码失败：{exc}") from exc


def _endpoint(operation_id: str, path: str) -> EndpointSpec[CjdkEnvelope]:
    normalized = path.strip()
    if not normalized or "REPLACE" in normalized.upper() or "TODO" in normalized.upper():
        raise RuntimeError(f"身份认证接口 path 尚未配置：{operation_id} -> {path!r}")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return EndpointSpec(
        operation_id=operation_id,
        method="POST",
        path=normalized,
        response_model=CjdkEnvelope,
        retry_mode=RetryMode.NEVER,
    )


def required_response_text(
    source: Mapping[str, Any],
    *keys: str,
    label: str | None = None,
) -> str:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    display = label or "/".join(keys)
    raise IdentityFlowError(f"外系统响应缺少{display}：候选字段={', '.join(keys)}")


def get_public_key(
    client: CjdkClient, settings: IdentitySettings, *, product_id: str, application_id: str
) -> tuple[str, str]:
    message = new_message("identity_get_public_key_v1")
    request = _request(message)
    request.update({"selblProdId": product_id, "businessNo": application_id})
    response = client.request(
        step="identity.get_public_key",
        endpoint=_endpoint("cjdk_jyrc.identity_get_public_key", settings.endpoint("getPublicKey")),
        message=message,
    )
    data = _response(response.rsp_body)
    return (
        required_response_text(data, "pubKey", label="pubKey"),
        required_response_text(data, "cryptFlowNo", label="cryptFlowNo"),
    )


def get_prepare_mobile(
    client: CjdkClient,
    settings: IdentitySettings,
    *,
    encrypted_customer_name: str,
    encrypted_identity_no: str,
    branch_no: str,
    card_no: str,
) -> str:
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
    response = client.request(
        step="identity.get_prepare_mobile",
        endpoint=_endpoint(
            "cjdk_jyrc.identity_get_prepare_mobile", settings.endpoint("getPrepareMobile")
        ),
        message=message,
    )
    return required_response_text(_response(response.rsp_body), "mobile", label="mobile")


def get_ali_sdk_params(
    client: CjdkClient, settings: IdentitySettings, *, product_id: str, application_id: str
) -> tuple[str, str]:
    message = new_message("identity_ali_sdk_params_v1")
    request = _request(message)
    request.update(
        {"traceNumber": application_id, "selblProdId": product_id, "applyNo": application_id}
    )
    response = client.request(
        step="identity.ali_sdk_params",
        endpoint=_endpoint(
            "cjdk_jyrc.identity_get_ali_sdk_params", settings.endpoint("getAliSdkParams")
        ),
        message=message,
    )
    data = _response(response.rsp_body)
    return (
        required_response_text(data, "traceNumber", label="traceNumber"),
        required_response_text(data, "license", label="license"),
    )


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
    message = new_message(settings.video_message_name(environment))
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
    response = client.request(
        step="identity.ali_video_check",
        endpoint=_endpoint(
            "cjdk_jyrc.identity_ali_video_check", settings.endpoint("aliVideoCheck")
        ),
        message=message,
    )
    data = _response(response.rsp_body)
    status = _first_text(response.rsp_head, "PROCESS_STATUS_CODE", "processStatusCode")
    return {
        "status": status,
        "message": _first_text(data, "verifyResultDtlMessage", "dataMessage", "message"),
        "captchaTraceId": _first_text(data, "captchTraceid", "captchaTraceid", "captchaTraceId"),
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
    response = client.request(
        step="identity.sms_code_send",
        endpoint=_endpoint("cjdk_jyrc.identity_sms_code_send", settings.endpoint("smsCodeSend")),
        message=message,
    )
    data = _response(response.rsp_body)
    pass_code_seq = required_response_text(data, "passCodeSeq", "passcodeSeq", label="passCodeSeq")
    return (_first_text(data, "resultMessage", "message"), pass_code_seq)


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
    response = client.request(
        step="identity.sms_code_check",
        endpoint=_endpoint("cjdk_jyrc.identity_sms_code_check", settings.endpoint("smsCodeCheck")),
        message=message,
    )
    return required_response_text(
        _response(response.rsp_body), "smsMessageId", label="smsMessageId"
    )


def verify_identity_card(
    client: CjdkClient, settings: IdentitySettings, *, context: IdentityContext
) -> dict[str, Any]:
    message = new_message("identity_card_verify_v1")
    request = _request(message)
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
    response = client.request(
        step="identity.card_verify",
        endpoint=_endpoint(
            "cjdk_jyrc.identity_card_verify", settings.endpoint("identityCardVerify")
        ),
        message=message,
    )
    data = _response(response.rsp_body)
    return {
        "success": True,
        "message": _first_text(data, "resultMessage", "message", "promptInf"),
        "rawResponse": data,
    }


def _response(body: Mapping[str, Any]) -> dict[str, Any]:
    data = body.get("response")
    if not isinstance(data, Mapping):
        raise IdentityFlowError("身份认证响应缺少 RSP_BODY.response 对象")
    return dict(data)


def _request(message: dict[str, Any]) -> dict[str, Any]:
    try:
        request = message["REQ_BODY"]["request"]
    except (KeyError, TypeError) as exc:
        raise IdentityFlowError("身份认证原始报文缺少 REQ_BODY.request") from exc
    if not isinstance(request, dict):
        raise IdentityFlowError("身份认证 REQ_BODY.request 必须是 JSON 对象")
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


class PhotoClient:
    """Photo service owns a completely independent httpx client and cookie jar."""

    def __init__(self, settings: PhotoEnvironmentSettings) -> None:
        self._settings = settings
        self._client: httpx.Client | None = None

    def __enter__(self) -> PhotoClient:
        self._client = httpx.Client(
            headers={
                "accept": "application/json, text/javascript, */*; q=0.01",
                "x-requested-with": "XMLHttpRequest",
                "user-agent": "Alkaid/identity-photo-client",
                **self._settings.headers,
            },
            timeout=self._settings.timeout_seconds,
            verify=self._settings.verify_ssl,
            follow_redirects=False,
        )
        return self

    def __exit__(self, *_: object) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None

    def post_message(self, *, path: str, message: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("PhotoClient 必须在 with 块中使用")
        url = urljoin(f"{self._settings.base_url.rstrip('/')}/", path.lstrip("/"))
        serialized = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        response = self._client.post(url, data={"REQ_MESSAGE": serialized})
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise IdentityFlowError(f"Photo 接口调用失败：{url}: {exc}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise IdentityFlowError(f"Photo 接口未返回 JSON：{url}") from exc
        if not isinstance(body, dict):
            raise IdentityFlowError(f"Photo 接口返回必须是 JSON 对象：{url}")
        return body

    def delete_certificate_photo(self, *, identity_no: str) -> None:
        message = _photo_message("delete_certificate_photo_v1")
        body = message.get("REQ_BODY")
        if not isinstance(body, dict):
            raise IdentityFlowError("photo.json 删除照片报文缺少 REQ_BODY 对象")
        body["idNo"] = identity_no
        self.post_message(path=self._settings.delete_path, message=message)


RAW_FILE = Path(__file__).with_name("raw_messages") / "photo.json"


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict[str, Any]]:
    raw = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("photo.json 必须是 JSON 对象")
    return {str(name): value for (name, value) in raw.items() if isinstance(value, dict)}


def _photo_message(name: str) -> dict[str, Any]:
    try:
        return deepcopy(_catalog()[name])
    except KeyError:
        raise RuntimeError(f"未配置 Photo 原始报文：{name}") from None


PASS_CODE_PATTERN = re.compile("passCode=(\\d+)")


class DcppClient:
    def __init__(self, settings_by_environment: dict[str, DcppEnvironmentSettings]) -> None:
        self._settings_by_environment = settings_by_environment
        self._client = httpx.Client(follow_redirects=False)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DcppClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def find_sms_code(self, *, environment: str, mobile: str, pass_code_seq: str) -> str:
        try:
            settings = self._settings_by_environment[environment.upper()]
        except KeyError:
            raise IdentityFlowError(f"未配置 {environment} 的短信日志查询") from None
        keyword = f"{mobile} SendStandardMessage passCodeSeq={pass_code_seq}"
        (start_ms, end_ms) = _today_range_ms()
        request_body = {
            "zone": settings.zone,
            "logHostPaths": list(settings.log_host_paths),
            "keyword": keyword,
            "from": str(start_ms),
            "to": str(end_ms),
            "asc": False,
            "size": 100,
            "searchAfter": [],
            "logNames": [],
            "interval": "15m",
            "need_data": True,
            "optimize": 1,
        }
        for attempt in range(1, settings.max_attempts + 1):
            response = self._client.post(
                settings.url,
                headers=settings.headers,
                json=request_body,
                timeout=settings.timeout_seconds,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                if attempt == settings.max_attempts:
                    raise IdentityFlowError(f"短信日志查询失败：{exc}") from exc
                time.sleep(settings.retry_interval_seconds)
                continue
            try:
                body = response.json()
            except ValueError as exc:
                raise IdentityFlowError("短信日志查询未返回 JSON") from exc
            code = _find_pass_code(body)
            if code:
                return code
            if attempt < settings.max_attempts:
                time.sleep(settings.retry_interval_seconds)
        raise IdentityFlowError(
            f"未查询到短信验证码：environment={environment}, passCodeSeq={pass_code_seq}"
        )


def _today_range_ms() -> tuple[int, int]:
    today = dt.date.today()
    start = dt.datetime.combine(today, dt.time.min)
    end = start + dt.timedelta(days=1)
    return (int(start.timestamp() * 1000), int(end.timestamp() * 1000))


def _find_pass_code(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    logs = body.get("logs")
    if not isinstance(logs, list):
        return None
    for item in logs:
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if not isinstance(message, str):
            continue
        match = PASS_CODE_PATTERN.search(message)
        if match:
            return match.group(1)
    return None
