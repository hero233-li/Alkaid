from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.jobs.models import TERMINAL_JOB_STATUSES, Job, JobLog, JobStatus


class JobConflict(ValueError):
    pass


class InvalidJobTransition(ValueError):
    pass


@dataclass(frozen=True)
class CreatedJob:
    job: Job
    created: bool


class JobRepository:
    @staticmethod
    def create(
        *,
        kind: str,
        name: str,
        product: str,
        payload: dict[str, Any],
        trace_id: str,
        idempotency_key: str,
        timeout_seconds: int,
        execution_config_version: int = 1,
        execution_config_snapshot: dict[str, Any] | None = None,
    ) -> CreatedJob:
        now = timezone.now()
        try:
            with transaction.atomic():
                job = Job.objects.create(
                    kind=kind,
                    name=name,
                    product=product,
                    payload=payload,
                    trace_id=trace_id,
                    idempotency_key=idempotency_key,
                    timeout_seconds=timeout_seconds,
                    execution_config_version=execution_config_version,
                    execution_config_snapshot=execution_config_snapshot or {},
                    deadline_at=now + timedelta(seconds=timeout_seconds),
                    expires_at=now + timedelta(hours=settings.JOB_RETENTION_HOURS),
                )
                JobRepository.add_log(job, "INFO", "任务已创建，等待执行", step="created")
                return CreatedJob(job=job, created=True)
        except IntegrityError as exc:
            try:
                job = Job.objects.get(idempotency_key=idempotency_key)
            except Job.DoesNotExist:
                raise exc from None
            if (
                job.kind != kind
                or job.name != name
                or job.product != product
                or job.payload != payload
            ):
                raise JobConflict("幂等键已被其他请求使用") from None
            return CreatedJob(job=job, created=False)

    @staticmethod
    def add_log(
        job: Job,
        level: str,
        message: str,
        *,
        step: str = "",
        celery_task_id: str = "",
        attempt: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JobLog | None:
        if JobLog.objects.filter(job=job).count() >= settings.JOB_MAX_LOGS:
            return None
        return JobLog.objects.create(
            job=job,
            level=level[:16].upper(),
            message=message,
            step=step,
            celery_task_id=celery_task_id,
            attempt=attempt or job.attempt_count,
            metadata=metadata or {},
        )

    @staticmethod
    def mark_running(job_id: int, celery_task_id: str) -> Job | None:
        with transaction.atomic():
            job = Job.objects.select_for_update().get(id=job_id)
            if job.status not in {JobStatus.PENDING, JobStatus.RETRYING}:
                return None
            job.status = JobStatus.RUNNING
            job.stage = "validate"
            job.progress = 10
            job.celery_task_id = celery_task_id
            job.error_message = ""
            job.save(
                update_fields=[
                    "status",
                    "stage",
                    "progress",
                    "celery_task_id",
                    "error_message",
                    "updated_at",
                ]
            )
            JobRepository.add_log(
                job,
                "INFO",
                f"第 {job.attempt_count} 次执行开始",
                step="validate",
                celery_task_id=celery_task_id,
            )
            return job

    @staticmethod
    def update_progress(job_id: int, *, stage: str, progress: int, message: str) -> Job:
        with transaction.atomic():
            job = Job.objects.select_for_update().get(id=job_id)
            if job.status == JobStatus.CANCEL_REQUESTED:
                raise InvalidJobTransition("任务已请求取消")
            if job.status != JobStatus.RUNNING:
                raise InvalidJobTransition(f"任务状态 {job.status} 不能更新进度")
            job.stage = stage
            job.progress = max(0, min(progress, 99))
            job.save(update_fields=["stage", "progress", "updated_at"])
            JobRepository.add_log(
                job,
                "INFO",
                message,
                step=stage,
                celery_task_id=job.celery_task_id,
            )
            return job

    @staticmethod
    def mark_success(job_id: int, result: dict[str, Any]) -> Job:
        return JobRepository._finish(
            job_id,
            status=JobStatus.SUCCESS,
            stage="completed",
            progress=100,
            result=result,
            error_message="",
            log_level="INFO",
            log_message="任务执行完成",
        )

    @staticmethod
    def mark_failed(job_id: int, error: str) -> Job:
        return JobRepository._finish(
            job_id,
            status=JobStatus.FAILED,
            stage="failed",
            progress=100,
            result={},
            error_message=error[:4000],
            log_level="ERROR",
            log_message=f"任务执行失败：{error[:1000]}",
        )

    @staticmethod
    def mark_cancelled(job_id: int, message: str = "任务已取消") -> Job:
        return JobRepository._finish(
            job_id,
            status=JobStatus.CANCELLED,
            stage="cancelled",
            progress=100,
            result={},
            error_message="",
            log_level="WARN",
            log_message=message,
        )

    @staticmethod
    def mark_timed_out(job_id: int, message: str = "任务执行超时") -> Job:
        return JobRepository._finish(
            job_id,
            status=JobStatus.TIMED_OUT,
            stage="timed_out",
            progress=100,
            result={},
            error_message=message,
            log_level="ERROR",
            log_message=message,
        )

    @staticmethod
    def _finish(
        job_id: int,
        *,
        status: str,
        stage: str,
        progress: int,
        result: dict[str, Any],
        error_message: str,
        log_level: str,
        log_message: str,
    ) -> Job:
        with transaction.atomic():
            job = Job.objects.select_for_update().get(id=job_id)
            job.status = status
            job.stage = stage
            job.progress = progress
            job.result = result
            job.error_message = error_message
            job.expires_at = timezone.now() + timedelta(hours=settings.JOB_RETENTION_HOURS)
            job.save(
                update_fields=[
                    "status",
                    "stage",
                    "progress",
                    "result",
                    "error_message",
                    "expires_at",
                    "updated_at",
                ]
            )
            JobRepository.add_log(
                job,
                log_level,
                log_message,
                step=stage,
                celery_task_id=job.celery_task_id,
            )
            return job

    @staticmethod
    def request_retry(job_id: int) -> Job:
        with transaction.atomic():
            job = Job.objects.select_for_update().get(id=job_id)
            if job.status not in {JobStatus.FAILED, JobStatus.TIMED_OUT, JobStatus.CANCELLED}:
                raise InvalidJobTransition("当前状态不允许重试")
            job.status = JobStatus.RETRYING
            job.stage = "queued"
            job.progress = 0
            job.error_message = ""
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
                    "attempt_count",
                    "celery_task_id",
                    "cancel_requested_at",
                    "deadline_at",
                    "updated_at",
                ]
            )
            JobRepository.add_log(job, "INFO", "任务已重新加入队列", step="queued")
            return job

    @staticmethod
    def request_cancel(job_id: int) -> Job:
        with transaction.atomic():
            job = Job.objects.select_for_update().get(id=job_id)
            if job.status in TERMINAL_JOB_STATUSES:
                return job
            if job.status in {JobStatus.PENDING, JobStatus.RETRYING}:
                job.status = JobStatus.CANCELLED
                job.stage = "cancelled"
                job.progress = 100
            elif job.status == JobStatus.RUNNING:
                job.status = JobStatus.CANCEL_REQUESTED
                job.stage = "cancel_requested"
            job.cancel_requested_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "stage",
                    "progress",
                    "cancel_requested_at",
                    "updated_at",
                ]
            )
            JobRepository.add_log(
                job,
                "WARN",
                "收到任务取消请求",
                step=job.stage,
                celery_task_id=job.celery_task_id,
            )
            return job


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
        "payload": job.payload,
        "result": job.result,
        "executionConfigVersion": job.execution_config_version,
        "errorMessage": job.error_message or None,
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
