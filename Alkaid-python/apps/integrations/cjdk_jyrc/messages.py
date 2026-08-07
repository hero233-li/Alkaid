import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

RAW_MESSAGE_ROOT = Path(__file__).with_name("raw_messages")


def new_message(name: str) -> dict[str, Any]:
    try:
        return deepcopy(_message_catalog()[name])
    except KeyError:
        raise KeyError(f"未配置 CJDK-JYRC 原始报文：{name}") from None


@lru_cache(maxsize=1)
def _message_catalog() -> dict[str, dict[str, Any]]:
    messages: dict[str, dict[str, Any]] = {}
    for path in sorted(RAW_MESSAGE_ROOT.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"CJDK-JYRC {path.name} 必须是 JSON 对象")
        for name, message in raw.items():
            if not isinstance(message, dict):
                raise ValueError(f"CJDK-JYRC 报文 {name} 必须是 JSON 对象")
            key = str(name)
            if key in messages:
                raise ValueError(f"CJDK-JYRC 原始报文重复：{key}")
            messages[key] = message
    return messages


def validate_message_catalog() -> dict[str, int]:
    catalog = _message_catalog()
    required = {
        "query_agreement_templates_v1",
        "query_preview_image_v1",
        "show_document_by_doc_id_v1",
        "identity_get_public_key_v1",
        "identity_get_prepare_mobile_v1",
        "identity_ali_sdk_params_v1",
        "identity_ali_video_check_u12_v1",
        "identity_ali_video_check_uc_v1",
        "identity_sms_code_send_v1",
        "identity_sms_code_check_v1",
        "identity_card_verify_v1",
    }
    missing = required - catalog.keys()
    if missing:
        raise ValueError(f"CJDK-JYRC 缺少原始报文：{', '.join(sorted(missing))}")
    return {"messages": len(catalog)}
