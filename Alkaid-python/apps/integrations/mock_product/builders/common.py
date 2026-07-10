from typing import Any


def req_body_envelope(
    request: dict[str, Any],
    *,
    app_id: str,
    env: str,
    req_head: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "REQ_BODY": {
            "appId": app_id,
            "env": env,
            "request": request,
        },
        "REQ_HEAD": req_head or {},
    }
