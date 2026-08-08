import base64
import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import parse_qs

import httpx

from apps.integrations.mock import MockTransportRouter

MOCK_TEMPLATE_NO = "2209201448031"
MOCK_PREVIEW_DOC_ID = "MOCK-DOC-ID-001"


def create_mock_transport() -> httpx.MockTransport:
    router = MockTransportRouter()
    router.register("GET", "/application-entry/", _open_application_entry, prefix=True)
    router.register("GET", "/h5/application/session/bootstrap", lambda _: _establish_session())
    router.register_matcher(
        lambda request: request.url.path.endswith("/queryAgreementTemplateInfoListEA.do"),
        _with_session_message(_query_agreements),
    )
    router.register_matcher(
        lambda request: request.url.path.endswith("/queryPreviewImage.ajax"),
        _with_session_message(_query_preview),
    )
    router.register_matcher(
        lambda request: request.url.path.endswith("/showDocumentByDocIdList.ajax"),
        _with_session_message(_show_document),
    )
    router.register(
        "POST",
        "/mock/identity/",
        _identity_request,
        prefix=True,
    )
    return router.transport()


def _open_application_entry(request: httpx.Request) -> httpx.Response:
    link_id = request.url.path.rsplit("/", 1)[-1]
    return httpx.Response(
        302,
        headers=[
            ("Location", f"/h5/application/session/bootstrap?linkId={link_id}"),
            ("Set-Cookie", "link_entry=mock-link-entry; Path=/; HttpOnly"),
        ],
    )


def _with_session_message(
    handler: Callable[[dict[str, object]], httpx.Response],
) -> Callable[[httpx.Request], httpx.Response]:
    def wrapped(request: httpx.Request) -> httpx.Response:
        _require_session_cookie(request)
        return handler(_request_message(request))

    return wrapped


def _identity_request(request: httpx.Request) -> httpx.Response:
    _require_session_cookie(request)
    return _identity_response(request.url.path, _request_message(request))


def _establish_session() -> httpx.Response:
    return httpx.Response(
        200,
        text="<html><body>mock product application</body></html>",
        headers=[
            ("Content-Type", "text/html;charset=UTF-8"),
            ("Set-Cookie", "token_id=mock-entry-token; Path=/; HttpOnly"),
            ("Set-Cookie", "JSESSIONID=mock-entry-session; Path=/; HttpOnly"),
            ("X-FCOS-SESSIONID", "mock-entry-fcos-session"),
            ("X-Token", "mock-entry-x-token"),
            ("X-Sd", "mock-entry-x-sd"),
        ],
    )


def _query_agreements(message: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "RSP_BODY": {
                "request": message["REQ_BODY"]["request"],
                "processStatusCode": "N",
                "response": {
                    "docAgreementTemplateInfoList": [
                        {
                            "docId": "MOCK-TEMPLATE-DOC-001",
                            "docName": "《交通银行个人经营性贷款个人信息处理授权书》",
                            "docType": "AULE0005",
                            "fcosTemplateNo": MOCK_TEMPLATE_NO,
                            "status": "1",
                            "orgCode": "01315999999",
                        }
                    ]
                },
            }
        },
        headers=[
            ("Content-Type", "text/javascript;charset=UTF-8"),
            ("Set-Cookie", "token_id=mock-token-cookie; Path=/; HttpOnly"),
            ("Set-Cookie", "JSESSIONID=mock-query-session; Path=/; HttpOnly"),
        ],
    )


def _query_preview(message: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "RSP_BODY": {
                "request": None,
                "REMOTE_CLIENT_ADDR": "127.0.0.1",
                "response": {
                    "successFlag": "Y",
                    "message": None,
                    "docId": MOCK_PREVIEW_DOC_ID,
                    "docList": [
                        {
                            "docId": MOCK_PREVIEW_DOC_ID,
                            "docName": "《交通银行个人经营性贷款个人信息处理授权书》",
                            "docType": "AULE0005",
                            "fcosTemplateNo": MOCK_TEMPLATE_NO,
                            "businessNo": "00000000",
                            "channel": "G",
                        }
                    ],
                    "imagePreviewNewSwitch": "1",
                    "loanProdLine": "PH",
                    "isExternalAgencies": "N",
                },
            },
            "RSP_HEAD": {
                "TRAN_SUCCESS": "1",
                "PROCESS_STATUS_CODE": "N",
            },
        },
        headers=[
            ("Content-Type", "text/javascript;charset=UTF-8"),
            ("Set-Cookie", "token_id=mock-token-cookie-2; Path=/; HttpOnly"),
            ("Set-Cookie", "JSESSIONID=mock-preview-session; Path=/; HttpOnly"),
            ("X-FCOS-SESSIONID", "mock-fcos-session"),
            ("X-Token", "mock-x-token"),
            ("X-Sd", "mock-x-sd"),
        ],
    )


def _show_document(message: dict[str, object]) -> httpx.Response:
    request_body = message["REQ_BODY"]["request"]
    document = base64.b64encode(b"%PDF-1.4\nmock agreement\n%%EOF").decode()
    return httpx.Response(
        200,
        json={
            "RSP_BODY": {
                "request": request_body,
                "downFile": document,
                "fileInfo": [
                    {
                        "fileName": "mock-agreement.pdf",
                        "downFile": document,
                        "resourceObjectDT": "20260731",
                        "resourceObjectPosition": "1",
                        "resourceObjectVers": "1",
                        "resourceObjectSN": "3918474601",
                        "url": None,
                    }
                ],
                "docSize": "0.029",
                "isExternalAgencies": "N",
                "successFlag": "Y",
            },
            "RSP_HEAD": {
                "TRAN_SUCCESS": "1",
                "PROCESS_STATUS_CODE": "N",
            },
        },
        headers=[
            ("Content-Type", "text/javascript;charset=UTF-8"),
            ("Set-Cookie", "JSESSIONID=mock-document-session; Path=/; HttpOnly"),
        ],
    )


def _identity_response(path: str, message: dict[str, object]) -> httpx.Response:
    responses: dict[str, dict[str, object]] = {
        "/mock/identity/public-key": {
            "pubKey": "MOCK-PUBLIC-KEY",
            "cryptFlowNo": "MOCK-CRYPT-FLOW-001",
        },
        "/mock/identity/prepare-mobile": {"mobile": "MOCK-ENC-MOBILE"},
        "/mock/identity/ali-sdk-params": {
            "traceNumber": "MOCK-FACE-TRACE-001",
            "license": "MOCK-FACE-LICENSE",
        },
        "/mock/identity/video-check": {
            "verifyResultDtlMessage": "mock face verification passed",
            "captchTraceid": "MOCK-CAPTCHA-TRACE-001",
        },
        "/mock/identity/sms-send": {
            "resultMessage": "mock sms sent",
            "passCodeSeq": "MOCK-PASS-CODE-001",
        },
        "/mock/identity/sms-check": {"smsMessageId": "MOCK-SMS-MESSAGE-001"},
        "/mock/identity/card-verify": {
            "resultMessage": "mock identity verification passed",
            "verified": True,
        },
    }
    response = responses.get(path)
    if response is None:
        return httpx.Response(404, json={"message": "mock identity endpoint not found"})
    return httpx.Response(
        200,
        json={
            "RSP_BODY": {
                "request": message["REQ_BODY"]["request"],
                "response": response,
            },
            "RSP_HEAD": {"PROCESS_STATUS_CODE": "N", "TRAN_SUCCESS": "1"},
        },
    )


def _request_message(request: httpx.Request) -> dict[str, object]:
    form = parse_qs(request.content.decode("utf-8"))
    raw = form.get("REQ_MESSAGE", [None])[0]
    if raw is None:
        raise AssertionError("REQ_MESSAGE is required")
    if form.get("biz_content", [None])[0] != raw:
        raise AssertionError("REQ_MESSAGE and biz_content must be identical")
    return json.loads(raw)


def _require_session_cookie(request: httpx.Request) -> None:
    cookie = request.headers.get("Cookie", "")
    if "JSESSIONID=" not in cookie or "token_id=" not in cookie:
        raise AssertionError("application session cookies were not carried forward")


def mock_submit_application(payload: Mapping[str, Any]) -> tuple[str, str, str]:
    """Deterministic startApply simulation owned by this feature."""

    name = _required_text(payload, "personName", "客户姓名")
    identity_no = _required_text(payload, "certificateNo", "证件号码")
    product = _required_text(payload, "product", "产品编号")
    digest = _digest(product, identity_no)
    return (
        f"MOCK-APPLY-{digest[:16]}",
        f"MOCK-ENC-{_digest(name)[:24]}",
        f"MOCK-ENC-{_digest(identity_no)[:32]}",
    )


def _digest(*values: str) -> str:
    return hashlib.sha256("\\x1f".join(values).encode()).hexdigest().upper()


def _required_text(payload: Mapping[str, Any], key: str, label: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"缺少{label}：{key}")
    return value
