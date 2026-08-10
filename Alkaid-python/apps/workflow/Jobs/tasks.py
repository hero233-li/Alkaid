from celery import shared_task

from apps.workflow.Jobs.services import reconcile_expired_jobs as reconcile_expired_job_records
from apps.workflow.Jobs.use_cases import cleanup_expired_jobs as cleanup_expired_job_records


@shared_task(name="apps.workflow.Jobs.tasks.reconcile_expired_jobs")
def reconcile_expired_jobs() -> dict[str, int]:
    return reconcile_expired_job_records()


@shared_task(name="apps.workflow.Jobs.tasks.cleanup_expired_jobs")
def cleanup_expired_jobs() -> dict[str, int]:
    return cleanup_expired_job_records()
