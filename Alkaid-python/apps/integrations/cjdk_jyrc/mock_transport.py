import base64
import json
from urllib.parse import parse_qs

import httpx


MOCK_TEMPLATE_NO = "2209201448031"
MOCK_PREVIEW_DOC_ID = "MOCK-DOC-ID-001"


def create_mock_transport() -> httpx.MockTransport:
    return httpx.MockTransport(_handle_request)


def _handle_request(request: httpx.Request) -> httpx.Response:
    message = _request_message(request)
    if request.url.path.endswith("/queryAgreementTemplateInfoListEA.do"):
        return _query_agreements(message)
    if request.url.path.endswith("/queryPreviewImage.ajax"):
        _require_session_cookie(request)
        return _query_preview(message)
    if request.url.path.endswith("/showDocumentByDocIdList.ajax"):
        _require_session_cookie(request)
        return _show_document(message)
    return httpx.Response(404, json={"message": "mock endpoint not found"})


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
        raise AssertionError("agreement session cookies were not carried forward")
