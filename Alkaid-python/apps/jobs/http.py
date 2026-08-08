import json
import logging
from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.jobs.models import ApiCallStatus, Job, JobApiCall
from apps.jobs.services import add_job_log

logger = logging.getLogger(__name__)


def limit_body(value: Any) -> tuple[Any, bool]:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    if len(encoded) <= settings.JOB_MAX_HTTP_BODY_BYTES:
        return value, False

    preview = encoded[: settings.JOB_MAX_HTTP_BODY_BYTES].decode(
        "utf-8",
        errors="ignore",
    )
    return {
        "truncated": True,
        "originalBytes": len(encoded),
        "preview": preview,
    }, True


def limit_text(value: str) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= settings.JOB_MAX_HTTP_BODY_BYTES:
        return value, False
    preview = encoded[: settings.JOB_MAX_HTTP_BODY_BYTES].decode("utf-8", errors="ignore")
    return f"{preview}\n<truncated originalBytes={len(encoded)}>", True


def format_log_value(value: Any) -> str:
    stored_value, _ = limit_body(value)
    if isinstance(stored_value, str):
        return stored_value
    return json.dumps(
        stored_value,
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
        raw_headers = dict(headers)
        stored_body, _ = limit_body(request_body)

        call = JobApiCall.objects.create(
            job=self.job,
            celery_task_id=self.job.celery_task_id,
            attempt=self.job.attempt_count,
            step=self.step,
            method=method.upper(),
            url=path,
            request_headers=raw_headers,
            request_body=stored_body,
        )

        add_job_log(
            self.job,
            "INFO",
            f"请求外部接口：{method.upper()} {path}",
            step=self.step,
            celery_task_id=self.job.celery_task_id,
            metadata={
                "callId": call.id,
                "event": "api_call_started",
            },
        )

        request_details = {
            "method": method.upper(),
            "url": path,
            "headers": raw_headers,
            "body": stored_body,
        }
        detail_message = f"外部请求原文：\n{format_log_value(request_details)}"
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
        raw_headers = dict(headers)
        stored_body, truncated = limit_body(response_body)

        call.response_status = status_code
        call.response_headers = raw_headers
        call.response_body = stored_body
        call.response_truncated = truncated
        call.duration_ms = max(0, duration_ms)
        call.status = ApiCallStatus.FAILED if error else ApiCallStatus.SUCCESS
        call.error_type = type(error).__name__ if error else ""
        call.error_message = limit_text(str(error))[0] if error else ""
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
            (f"外部接口{outcome}：{call.method} {call.url} -> {status_text} ({duration_ms}ms)"),
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
            "headers": raw_headers,
            "body": stored_body,
            "durationMs": duration_ms,
            "errorType": type(error).__name__ if error else None,
            "errorMessage": str(error) if error else None,
        }
        detail_message = f"外部响应原文：\n{format_log_value(response_details)}"
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
