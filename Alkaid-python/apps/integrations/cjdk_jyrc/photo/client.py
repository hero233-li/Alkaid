from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import requests

from apps.integrations.cjdk_jyrc.loan_step.identity_config import PhotoEnvironmentSettings


class PhotoServiceError(RuntimeError):
    pass


class PhotoClient:
    """Photo service owns a completely independent requests.Session."""

    def __init__(self, settings: PhotoEnvironmentSettings) -> None:
        self._settings = settings
        self._session: requests.Session | None = None

    def __enter__(self) -> "PhotoClient":
        session = requests.Session()
        session.headers.update(
            {
                "accept": "application/json, text/javascript, */*; q=0.01",
                "x-requested-with": "XMLHttpRequest",
                "user-agent": "Alkaid/identity-photo-client",
                **self._settings.headers,
            }
        )
        self._session = session
        return self

    def __exit__(self, *_: object) -> None:
        if self._session is not None:
            self._session.close()
        self._session = None

    def post_message(self, *, path: str, message: dict[str, Any]) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("PhotoClient 必须在 with 块中使用")

        url = urljoin(f"{self._settings.base_url.rstrip('/')}/", path.lstrip("/"))
        serialized = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        response = self._session.post(
            url,
            data={"REQ_MESSAGE": serialized},
            timeout=self._settings.timeout_seconds,
            verify=self._settings.verify_ssl,
        )
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise PhotoServiceError(f"Photo 接口调用失败：{url}: {exc}") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise PhotoServiceError(f"Photo 接口未返回 JSON：{url}") from exc
        if not isinstance(body, dict):
            raise PhotoServiceError(f"Photo 接口返回必须是 JSON 对象：{url}")
        return body
