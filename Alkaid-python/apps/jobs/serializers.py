from typing import Any

from apps.jobs.models import Job, JobLog


def serialize_log(log: JobLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "jobId": log.job_id,
        "level": log.level,
        "step": log.step or None,
        "message": log.message,
        "metadata": log.metadata,
        "createdAt": log.created_at.isoformat(),
    }


def serialize_job(job: Job, *, include_logs: bool = True) -> dict[str, Any]:
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
    return data
