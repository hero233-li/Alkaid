import base64
import hashlib
import json
from urllib.parse import parse_qs

import httpx

MOCK_TEMPLATE_NO = "2209201448031"
MOCK_PREVIEW_DOC_ID = "MOCK-DOC-ID-001"


def create_mock_transport() -> httpx.MockTransport:
    return httpx.MockTransport(_handle_request)


def _handle_request(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method == "POST" and path in {"/links/sun-code", "/links/dynamic"}:
        return _generate_application_link(request)
    if request.method == "GET" and path.startswith("/application-entry/"):
        link_id = path.rsplit("/", 1)[-1]
        return httpx.Response(
            302,
            headers=[
                ("Location", f"/h5/application/session/bootstrap?linkId={link_id}"),
                ("Set-Cookie", "link_entry=mock-link-entry; Path=/; HttpOnly"),
            ],
        )
    if request.method == "GET" and path == "/h5/application/session/bootstrap":
        return _establish_session()

    message = _request_message(request)
    if path.endswith("/queryAgreementTemplateInfoListEA.do"):
        _require_session_cookie(request)
        return _query_agreements(message)
    if path.endswith("/queryPreviewImage.ajax"):
        _require_session_cookie(request)
        return _query_preview(message)
    if path.endswith("/showDocumentByDocIdList.ajax"):
        _require_session_cookie(request)
        return _show_document(message)
    return httpx.Response(404, json={"message": "mock endpoint not found"})


def _generate_application_link(request: httpx.Request) -> httpx.Response:
    form = parse_qs(request.content.decode("utf-8"), keep_blank_values=True)
    required = {"msg_id", "sign", "timestamp", "REQ_MESSAGE", "biz_content"}
    if set(form) != required:
        return httpx.Response(400, json={"code": "INVALID_FORM", "data": {}})
    raw_message = form["REQ_MESSAGE"][0]
    if form["biz_content"][0] != raw_message:
        return httpx.Response(400, json={"code": "MESSAGE_MISMATCH", "data": {}})

    message = json.loads(raw_message)
    application_request = message["REQ_BODY"]["request"]
    digest = (
        hashlib.sha256(
            json.dumps(
                application_request,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        )
        .hexdigest()[:12]
        .upper()
    )
    link_id = f"LINK-{digest}"
    return httpx.Response(
        200,
        json={
            "code": "0000",
            "message": "处理成功",
            "data": {
                "internal_url": f"https://cjdk-jyrc.mock/application-entry/{link_id}",
                "external_url": f"https://cjdk-jyrc.mock/application-entry/{link_id}?scope=external",
            },
        },
    )


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
