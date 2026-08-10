import datetime as dt
import re
import time

import httpx

from apps.utils.http.config import DcppEnvironmentSettings

PASS_CODE_PATTERN = re.compile("passCode=(\\d+)")


class DcppClient:
    def __init__(self, settings_by_environment: dict[str, DcppEnvironmentSettings]) -> None:
        self._settings_by_environment = settings_by_environment
        self._client = httpx.Client(follow_redirects=False)

    def close(self) -> None:
        self._client.close()

    def find_sms_code(self, *, environment: str, mobile: str, pass_code_seq: str) -> str:
        settings = self._settings_by_environment[environment.upper()]
        (start_ms, end_ms) = _today_range_ms()
        request_body = {
            "zone": settings.zone,
            "logHostPaths": list(settings.log_host_paths),
            "keyword": f"{mobile} SendStandardMessage passCodeSeq={pass_code_seq}",
            "from": str(start_ms),
            "to": str(end_ms),
            "asc": False,
            "size": 100,
            "searchAfter": [],
            "logNames": [],
            "interval": "15m",
            "need_data": True,
            "optimize": 1,
        }
        for attempt in range(settings.max_attempts):
            response = self._client.post(
                settings.url,
                headers=settings.headers,
                json=request_body,
                timeout=settings.timeout_seconds,
            )
            response.raise_for_status()
            code = _find_pass_code(response.json())
            if code:
                return code
            if attempt + 1 < settings.max_attempts:
                time.sleep(settings.retry_interval_seconds)
        raise RuntimeError(
            f"未查询到短信验证码：environment={environment}, passCodeSeq={pass_code_seq}"
        )


def _today_range_ms() -> tuple[int, int]:
    today = dt.date.today()
    start = dt.datetime.combine(today, dt.time.min)
    end = start + dt.timedelta(days=1)
    return (int(start.timestamp() * 1000), int(end.timestamp() * 1000))


def _find_pass_code(body: dict) -> str | None:
    for item in body.get("logs", []):
        match = PASS_CODE_PATTERN.search(item.get("message", ""))
        if match:
            return match.group(1)
    return None
