import hashlib
import json
from urllib.parse import parse_qs

import httpx


def create_mock_product_transport(fixed_token: str) -> httpx.MockTransport:
    state = {"flow_token": "flow-token-v1"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = _request_payload(request)
        if path == "/auth/token":
            return httpx.Response(200, json={"data": {"token": state["flow_token"]}})

        if path == "/fixed/audit":
            if request.headers.get("X-Api-Token") != fixed_token:
                return httpx.Response(401, json={"code": "UNAUTHORIZED"})
            return _ok("固定 Token 校验成功", payload)

        expected = f"Bearer {state['flow_token']}"
        if request.headers.get("Authorization") != expected:
            return httpx.Response(401, json={"code": "UNAUTHORIZED"})
        if path == "/auth/rotate":
            state["flow_token"] = "flow-token-v2"
            return httpx.Response(
                200,
                headers={"X-New-Token": state["flow_token"]},
                json={"code": "0000", "message": "Token 已更新", "data": payload},
            )
        if path.startswith("/checks/"):
            return _ok(
                "产品检查通过",
                {"decision": "PASS", "ruleCode": path.rsplit("/", 1)[-1]},
            )
        if path == "/applications":
            request_message = payload.get("req_message")
            if not isinstance(request_message, dict):
                return httpx.Response(
                    400,
                    json={"code": "INVALID_MESSAGE", "message": "req_message 必须是对象"},
                )
            request_body = request_message.get("REQ_BODY")
            application_request = (
                request_body.get("request") if isinstance(request_body, dict) else None
            )
            if not isinstance(application_request, dict):
                return httpx.Response(
                    400,
                    json={"code": "INVALID_MESSAGE", "message": "REQ_BODY.request 缺失"},
                )
            order_no = str(application_request.get("orderNo") or "")
            suffix = order_no[-12:] if order_no else _digest(payload)
            return _ok(
                "产品申请成功",
                {
                    "applicationNo": f"APP-{suffix}",
                    "orderNo": order_no,
                    "acceptStatus": "ACCEPTED",
                },
            )
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "接口不存在"})

    return httpx.MockTransport(handler)


def _request_payload(request: httpx.Request) -> dict[str, object]:
    content = request.content.decode("utf-8") if request.content else ""
    if "application/x-www-form-urlencoded" in request.headers.get("Content-Type", ""):
        parsed = parse_qs(content, keep_blank_values=True)
        result: dict[str, object] = {}
        for name, values in parsed.items():
            value = values[-1]
            try:
                result[name] = json.loads(value)
            except json.JSONDecodeError:
                result[name] = value
        return result
    try:
        value = json.loads(content or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:12].upper()


def _ok(message: str, data: object) -> httpx.Response:
    return httpx.Response(200, json={"code": "0000", "message": message, "data": data})
