import hashlib
import json
from urllib.parse import parse_qs

import httpx


def create_application_link_mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path not in {"/links/sun-code", "/links/dynamic"}:
            return httpx.Response(404, json={"code": "NOT_FOUND", "message": "接口不存在"})
        form = parse_qs(request.content.decode(), keep_blank_values=True)
        if set(form) != {"msg_id", "sign", "timestamp", "REQ_MESSAGE", "biz_content"}:
            return httpx.Response(400, json={"code": "INVALID_FORM", "data": {}})
        if form["REQ_MESSAGE"] != form["biz_content"]:
            return httpx.Response(400, json={"code": "MESSAGE_MISMATCH", "data": {}})
        message = json.loads(form["REQ_MESSAGE"][0])
        application_request = message["REQ_BODY"]["request"]
        digest = _digest(application_request)
        product = str(application_request.get("product") or "unknown").upper()
        link_id = f"LINK-{product}-{digest}"
        path_kind = "dynamic" if request.url.path.endswith("dynamic") else "sun-code"
        return _ok(
            {
                "internal_url": f"https://internal.mock.local/apply/{link_id}",
                "external_url": f"https://apply.mock.local/{path_kind}/{link_id}",
            }
        )

    return httpx.MockTransport(handler)


def _digest(value: dict[str, object]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:10].upper()


def _ok(data: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, json={"code": "0000", "message": "处理成功", "data": data})
