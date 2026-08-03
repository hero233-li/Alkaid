from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.integrations.contracts import BusinessResponseError


def validate_cjdk_business_response(response_body: Any) -> None:
    if not isinstance(response_body, Mapping):
        return
    state = response_body.get("biz_state", response_body.get("bizState"))
    if str(state or "").strip().upper() not in {"F", "FAIL", "FAILED"}:
        return
    code = response_body.get("rsp_code", response_body.get("rspCode"))
    message = response_body.get("rsp_msg", response_body.get("rspMsg"))
    raise BusinessResponseError(
        f"CJDK-JYRC 业务处理失败：biz_state={state!r}；rsp_code={code!r}；rsp_msg={message!r}"
    )
