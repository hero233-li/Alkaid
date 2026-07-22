from typing import Any

from apps.jobs.models import Job, JobApiCall, JobLog


def serialize_log(log: JobLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "jobId": log.job_id,
        "taskId": log.celery_task_id or None,
        "attempt": log.attempt,
        "level": log.level,
        "step": log.step or None,
        "message": log.message,
        "metadata": log.metadata,
        "createdAt": log.created_at.isoformat(),
    }


def serialize_api_call(call: JobApiCall) -> dict[str, Any]:
    return {
        "id": call.id,
        "jobId": call.job_id,
        "taskId": call.celery_task_id or None,
        "attempt": call.attempt,
        "step": call.step or None,
        "method": call.method,
        "url": call.url,
        "requestHeaders": call.request_headers,
        "requestBody": call.request_body,
        "responseStatus": call.response_status,
        "responseHeaders": call.response_headers,
        "responseBody": call.response_body,
        "responseTruncated": call.response_truncated,
        "durationMs": call.duration_ms,
        "status": call.status,
        "errorType": call.error_type or None,
        "errorMessage": call.error_message or None,
        "startedAt": call.started_at.isoformat(),
        "finishedAt": call.finished_at.isoformat() if call.finished_at else None,
    }


def serialize_job(
    job: Job,
    *,
    include_logs: bool = True,
    include_payload: bool = False,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": job.id,
        "name": job.name,
        "product": job.product,
        "workflowId": str(job.workflow_id),
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "result": job.result,
        "executionConfigVersion": job.execution_config_version,
        "errorMessage": job.error_message or None,
        "errorCode": job.error_code or None,
        "traceId": job.trace_id,
        "idempotencyKey": job.idempotency_key,
        "attemptCount": job.attempt_count,
        "timeoutSeconds": job.timeout_seconds,
        "deadlineAt": job.deadline_at.isoformat() if job.deadline_at else None,
        "createdAt": job.created_at.isoformat(),
    }
    if include_logs:
        data["logs"] = [serialize_log(log) for log in job.logs.all()]
        data["apiCalls"] = [serialize_api_call(call) for call in job.api_calls.all()]
    if include_payload:
        data["payload"] = job.payload
    data["apiCallCount"] = getattr(job, "api_call_count", None)
    if data["apiCallCount"] is None:
        data["apiCallCount"] = job.api_calls.count()
    return data


def serialize_job_summary(job: Job) -> dict[str, Any]:
    return serialize_job(job, include_logs=False)
