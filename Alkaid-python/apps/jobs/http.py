import json
from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.jobs.models import ApiCallStatus, Job, JobApiCall
from apps.jobs.services import add_job_log

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "access_token",
    "password",
    "secret",
    "privatekey",
    "private_key",
    "myprivatekey",
    "certificateno",
    "certificate_no",
    "cardno",
    "card_no",
    "custnme",
    "phone",
    "idtyno",
    "sign",
    "req_message",
    "biz_content",
}


def _masked(value: Any) -> str:
    text = str(value)
    if len(text) <= 4:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def sanitize(value: Any, *, key: str = "") -> Any:
    normalized_key = key.lower().replace("-", "_")
    compact_key = normalized_key.replace("_", "")
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
        or "cookie" in compact_key
    ):
        return _masked(value)
    if isinstance(value, Mapping):
        return {
            str(item_key): sanitize(item, key=str(item_key)) for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def sanitize_and_limit(value: Any) -> tuple[Any, bool]:
    sanitized = sanitize(value)
    encoded = json.dumps(sanitized, ensure_ascii=False, default=str).encode("utf-8")
    if len(encoded) <= settings.JOB_MAX_HTTP_BODY_BYTES:
        return sanitized, False
    preview = encoded[: settings.JOB_MAX_HTTP_BODY_BYTES].decode("utf-8", errors="ignore")
    return {"truncated": True, "originalBytes": len(encoded), "preview": preview}, True


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
        safe_body, _ = sanitize_and_limit(request_body)
        call = JobApiCall.objects.create(
            job=self.job,
            celery_task_id=self.job.celery_task_id,
            attempt=self.job.attempt_count,
            step=self.step,
            method=method.upper(),
            url=path,
            request_headers=sanitize(dict(headers)),
            request_body=safe_body,
        )
        add_job_log(
            self.job,
            "INFO",
            f"请求外部接口：{method.upper()} {path}",
            step=self.step,
            celery_task_id=self.job.celery_task_id,
            metadata={"callId": call.id, "event": "api_call_started"},
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
        call = JobApiCall.objects.get(id=int(str(handle)), job=self.job)
        safe_body, truncated = sanitize_and_limit(response_body)
        call.response_status = status_code
        call.response_headers = sanitize(dict(headers))
        call.response_body = safe_body
        call.response_truncated = truncated
        call.duration_ms = max(0, duration_ms)
        call.status = ApiCallStatus.FAILED if error else ApiCallStatus.SUCCESS
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
        status_text = str(status_code) if status_code is not None else "无响应"
        add_job_log(
            self.job,
            "ERROR" if error else "INFO",
            f"外部接口{outcome}：{call.method} {call.url} -> {status_text} ({duration_ms}ms)",
            step=self.step,
            celery_task_id=self.job.celery_task_id,
            metadata={
                "callId": call.id,
                "event": "api_call_finished",
                "httpStatus": status_code,
                "durationMs": duration_ms,
            },
        )
