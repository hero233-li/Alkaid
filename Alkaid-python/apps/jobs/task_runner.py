from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

from apps.jobs.models import Job, JobStatus
from apps.jobs.services import (
    InvalidJobTransition,
    mark_job_cancelled,
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    mark_job_timed_out,
    update_job_progress,
)


@dataclass(frozen=True)
class JobTaskContext:
    job: Job

    def progress(self, *, stage: str, progress: int, message: str) -> None:
        update_job_progress(self.job.id, stage=stage, progress=progress, message=message)
        self.job.refresh_from_db()
        if self.job.status == JobStatus.CANCEL_REQUESTED:
            raise InvalidJobTransition("任务已请求取消")


def run_job_task(
    *,
    job_id: int,
    celery_task_id: str,
    queue_timeout_message: str,
    execute: Callable[[JobTaskContext], dict[str, Any]],
    on_error: Callable[[Job, Exception], None] | None = None,
) -> None:
    job = mark_job_running(job_id, celery_task_id)
    if job is None:
        return
    try:
        if job.deadline_at and job.deadline_at <= timezone.now():
            mark_job_timed_out(job.id, queue_timeout_message)
            return
        result = execute(JobTaskContext(job))
        mark_job_success(job.id, result)
    except InvalidJobTransition:
        mark_job_cancelled(job.id)
    except SoftTimeLimitExceeded:
        mark_job_timed_out(job.id)
        raise
    except Exception as exc:
        if on_error is not None:
            on_error(job, exc)
        mark_job_failed(job.id, f"{type(exc).__name__}: {exc}")
        raise
