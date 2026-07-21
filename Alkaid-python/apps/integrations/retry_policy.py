from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx


def retry_after_seconds(response: httpx.Response | None) -> float | None:
    if response is None:
        return None
    value = response.headers.get("Retry-After", "").strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def retry_delay(
    attempt: int,
    response: httpx.Response | None,
    *,
    backoff_seconds: float,
    max_backoff_seconds: float,
) -> float:
    retry_after = retry_after_seconds(response)
    if retry_after is not None:
        return min(retry_after, max_backoff_seconds)
    return min(backoff_seconds * (2**attempt), max_backoff_seconds)
