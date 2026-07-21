import json
from collections.abc import Mapping
from typing import Any

import httpx


def response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def serialize_form(form_data: Mapping[str, Any] | None) -> dict[str, str] | None:
    if form_data is None:
        return None
    serialized: dict[str, str] = {}
    for name, value in form_data.items():
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple)):
            serialized[name] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        elif isinstance(value, bool):
            serialized[name] = "true" if value else "false"
        else:
            serialized[name] = str(value)
    return serialized
