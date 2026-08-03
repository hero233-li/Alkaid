from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.jobs.models import Job, JobApiCall, JobLog, JobStatus
from apps.jobs.services import add_job_log, request_job_cancel, request_job_retry

EnqueueJob = Callable[[Job], None]
RevokeTask = Callable[[str], None]


def retry_job(job_id: int, *, enqueue: EnqueueJob) -> Job:
    job = request_job_retry(job_id)
    transaction.on_commit(lambda: enqueue(job))
    return job


def cancel_job(job_id: int, *, revoke: RevokeTask) -> Job:
    job = request_job_cancel(job_id)
    if not job.celery_task_id:
        return job
    try:
        revoke(job.celery_task_id)
    except Exception as exc:
        add_job_log(
            job,
            "WARN",
            f"向 Celery 发送撤销通知失败，将由任务状态阻止后续执行：{exc}",
            step="cancel_requested",
            celery_task_id=job.celery_task_id,
        )
    return job


def cleanup_expired_jobs(*, now: datetime | None = None) -> dict[str, int]:
    now = now or timezone.now()
    log_cutoff = now - timedelta(hours=settings.JOB_LOG_RETENTION_HOURS)
    deleted_logs, _ = JobLog.objects.filter(created_at__lt=log_cutoff).delete()
    deleted_calls, _ = JobApiCall.objects.filter(started_at__lt=log_cutoff).delete()
    deleted_jobs, _ = Job.objects.filter(
        status__in=[
            JobStatus.SUCCESS,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.TIMED_OUT,
        ],
        expires_at__lt=now,
    ).delete()
    return {"logs": deleted_logs, "api_calls": deleted_calls, "jobs": deleted_jobs}
