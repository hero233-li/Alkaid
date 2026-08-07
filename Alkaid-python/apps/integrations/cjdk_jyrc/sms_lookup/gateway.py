from __future__ import annotations

import datetime as dt
import re
import time
from typing import Any

import requests

from apps.integrations.cjdk_jyrc.loan_step.identity_config import (
    SmsLookupEnvironmentSettings,
)


PASS_CODE_PATTERN = re.compile(r"passCode=(\d+)")


class SmsLookupError(RuntimeError):
    pass


class DcppSmsCodeLookupGateway:
    def __init__(self, settings_by_environment: dict[str, SmsLookupEnvironmentSettings]) -> None:
        self._settings_by_environment = settings_by_environment
        self._session = requests.Session()

    def close(self) -> None:
        self._session.close()

    def find_sms_code(
        self,
        *,
        environment: str,
        mobile: str,
        pass_code_seq: str,
    ) -> str:
        try:
            settings = self._settings_by_environment[environment.upper()]
        except KeyError:
            raise SmsLookupError(f"未配置 {environment} 的短信日志查询") from None

        keyword = f"{mobile} SendStandardMessage passCodeSeq={pass_code_seq}"
        start_ms, end_ms = _today_range_ms()
        request_body = {
            "zone": settings.zone,
            "logHostPaths": list(settings.log_host_paths),
            "keyword": keyword,
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

        for attempt in range(1, settings.max_attempts + 1):
            response = self._session.post(
                settings.url,
                headers=settings.headers,
                json=request_body,
                timeout=settings.timeout_seconds,
            )
            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                if attempt == settings.max_attempts:
                    raise SmsLookupError(f"短信日志查询失败：{exc}") from exc
                time.sleep(settings.retry_interval_seconds)
                continue

            try:
                body = response.json()
            except ValueError as exc:
                raise SmsLookupError("短信日志查询未返回 JSON") from exc

            code = _find_pass_code(body)
            if code:
                return code
            if attempt < settings.max_attempts:
                time.sleep(settings.retry_interval_seconds)

        raise SmsLookupError(
            f"未查询到短信验证码：environment={environment}, passCodeSeq={pass_code_seq}"
        )


def _today_range_ms() -> tuple[int, int]:
    today = dt.date.today()
    start = dt.datetime.combine(today, dt.time.min)
    end = start + dt.timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _find_pass_code(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    logs = body.get("logs")
    if not isinstance(logs, list):
        return None
    for item in logs:
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if not isinstance(message, str):
            continue
        match = PASS_CODE_PATTERN.search(message)
        if match:
            return match.group(1)
    return None
