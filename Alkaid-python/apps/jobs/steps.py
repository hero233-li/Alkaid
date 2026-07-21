from typing import Any

from django.db import transaction

from apps.jobs.models import Job


def save_job_step(job: Job, step: str, value: Any) -> dict[str, Any]:
    """Persist one explicit business checkpoint in Job.result."""
    with transaction.atomic():
        locked = Job.objects.select_for_update().get(id=job.id)
        result = dict(locked.result or {})
        result[step] = value
        locked.result = result
        locked.save(update_fields=["result", "updated_at"])
    job.result = result
    return result
