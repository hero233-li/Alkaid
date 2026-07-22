from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.jobs.errors import InvalidJobTransition
from apps.jobs.models import Job, JobStatus


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
        if locked.status != JobStatus.RUNNING:
            raise InvalidJobTransition(f"任务状态 {locked.status} 不能保存执行步骤")
        if locked.celery_task_id != job.celery_task_id:
            raise InvalidJobTransition("当前 Worker 已失去任务执行权")
        if locked.deadline_at and locked.deadline_at <= timezone.now():
            raise InvalidJobTransition("任务已超过截止时间")
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
