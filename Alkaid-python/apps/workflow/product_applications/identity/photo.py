import json
from pathlib import Path
from urllib.parse import urljoin

import httpx

from apps.utils.http.config import PhotoEnvironmentSettings


class PhotoClient:
    """Photo service owns a completely independent httpx client and cookie jar."""

    def __init__(self, settings: PhotoEnvironmentSettings) -> None:
        self._settings = settings
        self._message_file = Path(__file__).parents[3] / "config" / "raw_messages" / "photo.json"
        self._client: httpx.Client | None = None

    def open(self) -> None:
        self._client = httpx.Client(
            headers={
                "accept": "application/json, text/javascript, */*; q=0.01",
                "x-requested-with": "XMLHttpRequest",
                "user-agent": "Alkaid/identity-photo-client",
                **self._settings.headers,
            },
            timeout=self._settings.timeout_seconds,
            verify=self._settings.verify_ssl,
            follow_redirects=False,
        )
    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None

    def delete_certificate_photo(self, *, identity_no: str) -> None:
        if self._client is None:
            raise RuntimeError("PhotoClient 必须在 with 块中使用")
        messages = json.loads(self._message_file.read_text(encoding="utf-8"))
        message = messages["delete_certificate_photo_v1"]
        message["REQ_BODY"]["idNo"] = identity_no
        url = urljoin(
            f"{self._settings.base_url.rstrip('/')}/",
            self._settings.delete_path.lstrip("/"),
        )
        serialized = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        response = self._client.post(url, data={"REQ_MESSAGE": serialized})
        response.raise_for_status()
