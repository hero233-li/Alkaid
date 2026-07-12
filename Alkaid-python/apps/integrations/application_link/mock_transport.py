import hashlib
import json

import httpx


def create_application_link_mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = _read_json(request)
        if request.url.path == "/applications":
            product = str(payload.get("product") or "unknown").replace(" ", "-")
            digest = _digest(payload)
            return _ok(
                {
                    "application_no": f"LINK-{product.upper()}-{digest}",
                    "status": "CREATED",
                }
            )
        if request.url.path in {"/links/sun-code", "/links/dynamic"}:
            application_no = str(payload.get("application_no") or "LINK-UNKNOWN")
            path_kind = "dynamic" if request.url.path.endswith("dynamic") else "sun-code"
            return _ok(
                {
                    "internal_url": f"https://internal.mock.local/apply/{application_no}",
                    "external_url": f"https://apply.mock.local/{path_kind}/{application_no}",
                    "status": "ACTIVE",
                }
            )
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "接口不存在"})

    return httpx.MockTransport(handler)


def _read_json(request: httpx.Request) -> dict[str, object]:
    try:
        value = json.loads(request.content.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _digest(value: dict[str, object]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:10].upper()


def _ok(data: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, json={"code": "0000", "message": "处理成功", "data": data})
