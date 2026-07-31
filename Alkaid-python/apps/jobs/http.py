import json
import logging
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.utils import timezone

from apps.jobs.models import ApiCallStatus, Job, JobApiCall
from apps.jobs.services import add_job_log

logger = logging.getLogger(__name__)

JSON_MESSAGE_KEYS = {
    "req_message",
    "biz_content",
}
URL_KEYS = {
    "url",
    "internal_url",
    "internalurl",
    "external_url",
    "externalurl",
    "applicationurl",
    "finalurl",
}
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "token_id",
    "access_token",
    "password",
    "secret",
    "privatekey",
    "private_key",
    "myprivatekey",
    "apigwpublickey",
    "apigw_public_key",
    "certificateno",
    "certificate_no",
    "cardno",
    "card_no",
    "custnme",
    "phone",
    "idtyno",
    "sign",
    "x_fcos_sessionid",
    "x_sd",
    "x_token",
    "jsessionid",
    "sessionid",
}
OMITTED_CONTENT_KEYS = {
    "downfile",
    "down_file",
}

_TEXT_SECRET_PATTERNS = (
    re.compile(
        r'(?i)("?(?:myPrivateKey|privateKey|apigwPublicKey|'
        r'certificateNo|cardNo|phone|token_id|JSESSIONID|'
        r'X-Token|X-FCOS-SESSIONID|X-Sd)"?\s*[:=]\s*)'
        r'("[^"]*"|[^,\s;&]+)'
    ),
    re.compile(r"(?i)([?&](?:auth|token|token_id)=)[^&#\s]+"),
)


def _masked(value: Any) -> str:
    text = str(value)
    if len(text) <= 4:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def sanitize_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return sanitize_text(value)
    if not parsed.scheme or not parsed.netloc:
        return sanitize_text(value)

    query_items: list[tuple[str, str]] = []
    for name, item_value in parse_qsl(
        parsed.query,
        keep_blank_values=True,
    ):
        compact_name = name.lower().replace("-", "_").replace("_", "")
        if (
            "auth" in compact_name
            or "token" in compact_name
            or "session" in compact_name
            or "password" in compact_name
            or "secret" in compact_name
        ):
            query_items.append((name, _masked(item_value)))
        else:
            query_items.append((name, item_value))

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_items, doseq=True),
            parsed.fragment,
        )
    )


def sanitize_text(value: str) -> str:
    result = value
    for pattern in _TEXT_SECRET_PATTERNS:
        result = pattern.sub(lambda match: match.group(1) + '"***"', result)
    return result


def sanitize(value: Any, *, key: str = "") -> Any:
    normalized_key = key.lower().replace("-", "_")
    compact_key = normalized_key.replace("_", "")

    if normalized_key in JSON_MESSAGE_KEYS and isinstance(value, str):
        try:
            return sanitize(json.loads(value))
        except (TypeError, ValueError):
            return sanitize_text(value)

    if compact_key in {item.replace("_", "") for item in URL_KEYS}:
        return sanitize_url(str(value))

    if compact_key in {
        item.replace("_", "")
        for item in OMITTED_CONTENT_KEYS
    }:
        size = len(str(value))
        return f"<binary/base64 content omitted: {size} chars>"

    if (
        normalized_key in SENSITIVE_KEYS
        or compact_key in SENSITIVE_KEYS
        or "phone" in compact_key
        or "certificate" in compact_key
        or "card" in compact_key
        or "token" in compact_key
        or "authorization" in compact_key
        or "password" in compact_key
        or "secret" in compact_key
        or "privatekey" in compact_key
        or "publickey" in compact_key
        or "cookie" in compact_key
        or "sessionid" in compact_key
    ):
        return _masked(value)

    if isinstance(value, Mapping):
        return {
            str(item_key): sanitize(item, key=str(item_key))
            for item_key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]

    if isinstance(value, str):
        return sanitize_text(value)

    if value is None or isinstance(value, (int, float, bool)):
        return value

    return sanitize_text(str(value))


def sanitize_and_limit(value: Any) -> tuple[Any, bool]:
    sanitized = sanitize(value)
    encoded = json.dumps(
        sanitized,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    if len(encoded) <= settings.JOB_MAX_HTTP_BODY_BYTES:
        return sanitized, False

    preview = encoded[: settings.JOB_MAX_HTTP_BODY_BYTES].decode(
        "utf-8",
        errors="ignore",
    )
    return {
        "truncated": True,
        "originalBytes": len(encoded),
        "preview": preview,
    }, True


def format_log_value(value: Any) -> str:
    safe_value, _ = sanitize_and_limit(value)
    if isinstance(safe_value, str):
        return safe_value
    return json.dumps(
        safe_value,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


class JobHttpCallObserver:
    def __init__(self, job: Job, *, step: str) -> None:
        self.job = job
        self.step = step

    def started(
        self,
        *,
        method: str,
        path: str,
        headers: Mapping[str, str],
        request_body: Any,
    ) -> object:
        safe_headers = sanitize(dict(headers))
        safe_body, _ = sanitize_and_limit(request_body)

        call = JobApiCall.objects.create(
            job=self.job,
            celery_task_id=self.job.celery_task_id,
            attempt=self.job.attempt_count,
            step=self.step,
            method=method.upper(),
            url=sanitize_url(path),
            request_headers=safe_headers,
            request_body=safe_body,
        )

        add_job_log(
            self.job,
            "INFO",
            f"请求外部接口：{method.upper()} {sanitize_url(path)}",
            step=self.step,
            celery_task_id=self.job.celery_task_id,
            metadata={
                "callId": call.id,
                "event": "api_call_started",
            },
        )

        request_details = {
            "method": method.upper(),
            "url": sanitize_url(path),
            "headers": safe_headers,
            "body": safe_body,
        }
        detail_message = (
            "外部请求内容（敏感值已脱敏）：\n"
            f"{format_log_value(request_details)}"
        )
        add_job_log(
            self.job,
            "INFO",
            detail_message,
            step=self.step,
            celery_task_id=self.job.celery_task_id,
            metadata={
                "callId": call.id,
                "event": "api_call_request_body",
            },
        )
        logger.info(
            "external_call_request\n%s",
            format_log_value(request_details),
        )
        return call.id

    def finished(
        self,
        handle: object,
        *,
        status_code: int | None,
        headers: Mapping[str, str],
        response_body: Any,
        duration_ms: int,
        error: Exception | None,
    ) -> None:
        call = JobApiCall.objects.get(
            id=int(str(handle)),
            job=self.job,
        )
        safe_headers = sanitize(dict(headers))
        safe_body, truncated = sanitize_and_limit(response_body)

        call.response_status = status_code
        call.response_headers = safe_headers
        call.response_body = safe_body
        call.response_truncated = truncated
        call.duration_ms = max(0, duration_ms)
        call.status = (
            ApiCallStatus.FAILED
            if error
            else ApiCallStatus.SUCCESS
        )
        call.error_type = type(error).__name__ if error else ""
        call.error_message = str(error)[:4000] if error else ""
        call.finished_at = timezone.now()
        call.save(
            update_fields=[
                "response_status",
                "response_headers",
                "response_body",
                "response_truncated",
                "duration_ms",
                "status",
                "error_type",
                "error_message",
                "finished_at",
            ]
        )

        outcome = "失败" if error else "成功"
        status_text = (
            str(status_code)
            if status_code is not None
            else "无响应"
        )
        add_job_log(
            self.job,
            "ERROR" if error else "INFO",
            (
                f"外部接口{outcome}："
                f"{call.method} {call.url} -> "
                f"{status_text} ({duration_ms}ms)"
            ),
            step=self.step,
            celery_task_id=self.job.celery_task_id,
            metadata={
                "callId": call.id,
                "event": "api_call_finished",
                "httpStatus": status_code,
                "durationMs": duration_ms,
            },
        )

        response_details = {
            "statusCode": status_code,
            "headers": safe_headers,
            "body": safe_body,
            "durationMs": duration_ms,
            "errorType": type(error).__name__ if error else None,
            "errorMessage": str(error) if error else None,
        }
        detail_message = (
            "外部响应内容（敏感值已脱敏）：\n"
            f"{format_log_value(response_details)}"
        )
        add_job_log(
            self.job,
            "ERROR" if error else "INFO",
            detail_message,
            step=self.step,
            celery_task_id=self.job.celery_task_id,
            metadata={
                "callId": call.id,
                "event": "api_call_response_body",
            },
        )

        log_method = logger.error if error else logger.info
        log_method(
            "external_call_response\n%s",
            format_log_value(response_details),
        )
