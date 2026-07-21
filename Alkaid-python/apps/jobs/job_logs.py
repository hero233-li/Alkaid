from typing import Any

from django.conf import settings

from apps.jobs.models import Job, JobLog


def add_job_log(
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
