from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.jobs.job_logs import add_job_log
from apps.jobs.models import TERMINAL_JOB_STATUSES, Job, JobStatus


def reconcile_expired_jobs(*, now: datetime | None = None) -> dict[str, int]:
    now = now or timezone.now()
    candidate_ids = list(
        Job.objects.filter(
            status__in=[
                JobStatus.PENDING,
                JobStatus.RETRYING,
                JobStatus.RUNNING,
                JobStatus.CANCEL_REQUESTED,
            ],
            deadline_at__isnull=False,
            deadline_at__lte=now,
        )
        .order_by("deadline_at", "id")
        .values_list("id", flat=True)[: max(1, settings.JOB_RECONCILE_BATCH_SIZE)]
    )
    counts = {"cancelled": 0, "timed_out": 0}
    for job_id in candidate_ids:
        with transaction.atomic():
            try:
                job = Job.objects.select_for_update().get(id=job_id)
            except Job.DoesNotExist:
                continue
            if (
                job.status in TERMINAL_JOB_STATUSES
                or job.deadline_at is None
                or job.deadline_at > now
            ):
                continue
            if job.status == JobStatus.CANCEL_REQUESTED:
                job.status = JobStatus.CANCELLED
                job.stage = "cancelled"
                level, message, key = "WARN", "任务取消请求已由后台巡检收敛", "cancelled"
            elif job.status in {JobStatus.PENDING, JobStatus.RETRYING, JobStatus.RUNNING}:
                job.status = JobStatus.TIMED_OUT
                job.stage = "timed_out"
                job.error_message = "任务超过截止时间，由后台巡检标记为超时"
                level, message, key = "ERROR", job.error_message, "timed_out"
            else:
                continue
            job.progress = 100
            job.expires_at = now + timedelta(hours=settings.JOB_RETENTION_HOURS)
            job.save(
                update_fields=[
                    "status",
                    "stage",
                    "progress",
                    "error_message",
                    "expires_at",
                    "updated_at",
                ]
            )
            add_job_log(job, level, message, step=job.stage, celery_task_id=job.celery_task_id)
            counts[key] += 1
    return counts
