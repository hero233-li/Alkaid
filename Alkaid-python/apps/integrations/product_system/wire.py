def build_five_field_form(
    *, msg_id: str, sign: str, timestamp: str, message: str
) -> dict[str, str]:
    return {
        "msg_id": msg_id,
        "sign": sign,
        "timestamp": timestamp,
        "REQ_MESSAGE": message,
        "biz_content": message,
    }


def build_req_form(message: str) -> dict[str, str]:
    return {"REQ_MESSAGE": message}
