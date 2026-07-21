from collections.abc import Callable
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

from apps.jobs.models import Job
from apps.jobs.services import (
    InvalidJobTransition,
    mark_job_cancelled,
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    mark_job_timed_out,
)


def run_menu_task(
    *,
    job_id: int,
    celery_task_id: str,
    queue_timeout_message: str,
    execute: Callable[[Job], dict[str, Any]],
    on_error: Callable[[Job, Exception], None] | None = None,
) -> None:
    job = mark_job_running(job_id, celery_task_id)
    if job is None:
        return
    try:
        if job.deadline_at and job.deadline_at <= timezone.now():
            mark_job_timed_out(job.id, queue_timeout_message)
            return
        result = execute(job)
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
