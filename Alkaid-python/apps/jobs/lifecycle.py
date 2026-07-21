from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.jobs.errors import InvalidJobTransition
from apps.jobs.job_logs import add_job_log
from apps.jobs.models import TERMINAL_JOB_STATUSES, Job, JobStatus
from apps.jobs.specs import is_non_retryable_job

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    JobStatus.PENDING: frozenset(
        {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT}
    ),
    JobStatus.RETRYING: frozenset(
        {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT}
    ),
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.SUCCESS,
            JobStatus.FAILED,
            JobStatus.TIMED_OUT,
            JobStatus.CANCEL_REQUESTED,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.CANCEL_REQUESTED: frozenset(
        {JobStatus.CANCELLED, JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.TIMED_OUT}
    ),
    JobStatus.FAILED: frozenset({JobStatus.RETRYING}),
    JobStatus.TIMED_OUT: frozenset({JobStatus.RETRYING}),
    JobStatus.CANCELLED: frozenset({JobStatus.RETRYING}),
    JobStatus.SUCCESS: frozenset(),
}


def ensure_job_transition(current: str, target: str) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidJobTransition(f"任务状态不允许从 {current} 转换为 {target}")


def mark_job_running(job_id: int, celery_task_id: str) -> Job | None:
    with transaction.atomic():
        job = Job.objects.select_for_update().get(id=job_id)
        if job.status == JobStatus.CANCEL_REQUESTED:
            ensure_job_transition(job.status, JobStatus.CANCELLED)
            job.status = JobStatus.CANCELLED
            job.stage = "cancelled"
            job.progress = 100
            job.save(update_fields=["status", "stage", "progress", "updated_at"])
            add_job_log(
                job,
                "WARN",
                "任务在重新执行前已收到取消请求",
                step="cancelled",
                celery_task_id=celery_task_id,
            )
            return None
        if job.status == JobStatus.RUNNING and job.celery_task_id == celery_task_id:
            add_job_log(
                job,
                "WARN",
                "Worker 中断后恢复同一任务",
                step=job.stage,
                celery_task_id=celery_task_id,
            )
            return job
        if job.status not in {JobStatus.PENDING, JobStatus.RETRYING}:
            return None
        ensure_job_transition(job.status, JobStatus.RUNNING)
        job.status = JobStatus.RUNNING
        job.stage = "validate"
        job.progress = 10
        job.celery_task_id = celery_task_id
        job.error_message = ""
        job.error_code = ""
        job.save(
            update_fields=[
                "status",
                "stage",
                "progress",
                "celery_task_id",
                "error_message",
                "error_code",
                "updated_at",
            ]
        )
        add_job_log(
            job,
            "INFO",
            f"第 {job.attempt_count} 次执行开始",
            step="validate",
            celery_task_id=celery_task_id,
        )
        return job


def update_job_progress(job_id: int, *, stage: str, progress: int, message: str) -> Job:
    with transaction.atomic():
        job = Job.objects.select_for_update().get(id=job_id)
        if job.status == JobStatus.CANCEL_REQUESTED:
            raise InvalidJobTransition("任务已请求取消")
        if job.status != JobStatus.RUNNING:
            raise InvalidJobTransition(f"任务状态 {job.status} 不能更新进度")
        job.stage = stage
        job.progress = max(0, min(progress, 99))
        job.save(update_fields=["stage", "progress", "updated_at"])
        add_job_log(job, "INFO", message, step=stage, celery_task_id=job.celery_task_id)
        return job


def mark_job_success(job_id: int, result: dict[str, Any]) -> Job:
    return _finish_job(
        job_id,
        status=JobStatus.SUCCESS,
        stage="completed",
        progress=100,
        result=result,
        error_message="",
        error_code="",
        log_level="INFO",
        log_message="任务执行完成",
    )


def mark_job_failed(job_id: int, error: str, *, error_code: str = "internal_error") -> Job:
    return _finish_job(
        job_id,
        status=JobStatus.FAILED,
        stage="failed",
        progress=100,
        result=None,
        error_message=error[:4000],
        error_code=error_code,
        log_level="ERROR",
        log_message=f"任务执行失败：{error[:1000]}",
    )


def mark_job_cancelled(job_id: int, message: str = "任务已取消") -> Job:
    return _finish_job(
        job_id,
        status=JobStatus.CANCELLED,
        stage="cancelled",
        progress=100,
        result=None,
        error_message="",
        error_code="",
        log_level="WARN",
        log_message=message,
    )


def mark_job_timed_out(job_id: int, message: str = "任务执行超时") -> Job:
    return _finish_job(
        job_id,
        status=JobStatus.TIMED_OUT,
        stage="timed_out",
        progress=100,
        result=None,
        error_message=message,
        error_code="job_timed_out",
        log_level="ERROR",
        log_message=message,
    )


def _finish_job(
    job_id: int,
    *,
    status: str,
    stage: str,
    progress: int,
    result: dict[str, Any] | None,
    error_message: str,
    error_code: str,
    log_level: str,
    log_message: str,
) -> Job:
    with transaction.atomic():
        job = Job.objects.select_for_update().get(id=job_id)
        if job.status in TERMINAL_JOB_STATUSES:
            return job
        ensure_job_transition(job.status, status)
        job.status = status
        job.stage = stage
        job.progress = progress
        if result is not None:
            job.result = result
        job.error_message = error_message
        job.error_code = error_code
        job.expires_at = timezone.now() + timedelta(hours=settings.JOB_RETENTION_HOURS)
        update_fields = [
            "status",
            "stage",
            "progress",
            "error_message",
            "error_code",
            "expires_at",
            "updated_at",
        ]
        if result is not None:
            update_fields.append("result")
        job.save(update_fields=update_fields)
        add_job_log(job, log_level, log_message, step=stage, celery_task_id=job.celery_task_id)
        return job


def request_job_retry(job_id: int) -> Job:
    with transaction.atomic():
        job = Job.objects.select_for_update().get(id=job_id)
        if job.status not in {JobStatus.FAILED, JobStatus.TIMED_OUT, JobStatus.CANCELLED}:
            raise InvalidJobTransition("当前状态不允许重试")
        if is_non_retryable_job(job.kind, job.payload):
            raise InvalidJobTransition(
                "该任务包含未确认幂等能力的外系统写操作，禁止重试；请先核对外系统结果"
            )
        ensure_job_transition(job.status, JobStatus.RETRYING)
        job.status = JobStatus.RETRYING
        job.stage = "queued"
        job.progress = 0
        job.error_message = ""
        job.error_code = ""
        job.attempt_count += 1
        job.celery_task_id = ""
        job.cancel_requested_at = None
        job.deadline_at = timezone.now() + timedelta(seconds=job.timeout_seconds)
        job.save(
            update_fields=[
                "status",
                "stage",
                "progress",
                "error_message",
                "error_code",
                "attempt_count",
                "celery_task_id",
                "cancel_requested_at",
                "deadline_at",
                "updated_at",
            ]
        )
        add_job_log(job, "INFO", "任务已重新加入队列", step="queued")
        return job


def request_job_cancel(job_id: int) -> Job:
    with transaction.atomic():
        job = Job.objects.select_for_update().get(id=job_id)
        if job.status in TERMINAL_JOB_STATUSES:
            return job
        if job.status == JobStatus.RUNNING and is_non_retryable_job(job.kind, job.payload):
            raise InvalidJobTransition(
                "该任务已进入未确认幂等能力的外系统写阶段，不能取消；请等待结果并核对外系统状态"
            )
        if job.status in {JobStatus.PENDING, JobStatus.RETRYING}:
            ensure_job_transition(job.status, JobStatus.CANCELLED)
            job.status = JobStatus.CANCELLED
            job.stage = "cancelled"
            job.progress = 100
        elif job.status == JobStatus.RUNNING:
            ensure_job_transition(job.status, JobStatus.CANCEL_REQUESTED)
            job.status = JobStatus.CANCEL_REQUESTED
            job.stage = "cancel_requested"
        job.cancel_requested_at = timezone.now()
        job.save(update_fields=["status", "stage", "progress", "cancel_requested_at", "updated_at"])
        add_job_log(
            job, "WARN", "收到任务取消请求", step=job.stage, celery_task_id=job.celery_task_id
        )
        return job
