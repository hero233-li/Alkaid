from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.jobs.models import Job, JobApiCall, JobLog, JobStatus
from apps.jobs.services import reconcile_expired_jobs as reconcile_expired_job_records


@shared_task(name="apps.jobs.tasks.reconcile_expired_jobs")
def reconcile_expired_jobs() -> dict[str, int]:
    return reconcile_expired_job_records()


@shared_task(name="apps.jobs.tasks.cleanup_expired_jobs")
def cleanup_expired_jobs() -> dict[str, int]:
    now = timezone.now()
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
