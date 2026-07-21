from typing import Any

from django.db import transaction

from apps.jobs.models import Job


def save_job_step(
    job: Job,
    step: str,
    value: Any,
    *,
    stage: str | None = None,
    progress: int | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Persist one business checkpoint together with visible Job progress."""
    with transaction.atomic():
        locked = Job.objects.select_for_update().get(id=job.id)
        result = dict(locked.result or {})
        result[step] = value
        locked.result = result
        update_fields = ["result", "updated_at"]
        if stage is not None:
            locked.stage = stage
            update_fields.append("stage")
        if progress is not None:
            locked.progress = max(0, min(progress, 99))
            update_fields.append("progress")
        locked.save(update_fields=update_fields)
        if message:
            from apps.jobs.services import add_job_log

            add_job_log(
                locked,
                "INFO",
                message,
                step=stage or step,
                celery_task_id=locked.celery_task_id,
            )
    job.result = result
    job.stage = locked.stage
    job.progress = locked.progress
    return result
