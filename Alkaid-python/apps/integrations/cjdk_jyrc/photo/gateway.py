from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.integrations.cjdk_jyrc.loan_step.identity_config import PhotoEnvironmentSettings
from apps.integrations.cjdk_jyrc.photo.client import PhotoClient


RAW_FILE = Path(__file__).resolve().parents[1] / "raw_messages" / "photo.json"


class CjdkPhotoGateway:
    def __init__(
        self,
        *,
        client: PhotoClient,
        settings: PhotoEnvironmentSettings,
    ) -> None:
        self._client = client
        self._settings = settings

    def delete_certificate_photo(self, *, identity_no: str) -> None:
        message = _photo_message("delete_certificate_photo_v1")
        try:
            body = message["REQ_BODY"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("photo.json 删除照片报文缺少 REQ_BODY") from exc
        if not isinstance(body, dict):
            raise RuntimeError("photo.json REQ_BODY 必须是 JSON 对象")
        body["idNo"] = identity_no
        self._client.post_message(path=self._settings.delete_path, message=message)


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict[str, Any]]:
    raw = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("photo.json 必须是 JSON 对象")
    return {str(name): value for name, value in raw.items() if isinstance(value, dict)}


def _photo_message(name: str) -> dict[str, Any]:
    try:
        return deepcopy(_catalog()[name])
    except KeyError:
        raise RuntimeError(f"未配置 Photo 原始报文：{name}") from None
