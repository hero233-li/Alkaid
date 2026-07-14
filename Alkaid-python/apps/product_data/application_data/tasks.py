from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from apps.jobs.models import JobStatus
from apps.jobs.services import (
    InvalidJobTransition,
    mark_job_cancelled,
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    mark_job_timed_out,
    update_job_progress,
)
from apps.product_data.application_data.services import execute_application_data_generation


@shared_task(
    bind=True,
    name="apps.product_data.application_data.tasks.execute_application_data",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.APPLICATION_DATA_TIMEOUT_SECONDS,
    time_limit=settings.APPLICATION_DATA_TIMEOUT_SECONDS + 10,
)
def execute_application_data_task(self, job_id: int) -> None:
    job = mark_job_running(job_id, str(self.request.id or "local-eager-task"))
    if job is None:
        return
    try:
        if job.deadline_at and job.deadline_at <= timezone.now():
            mark_job_timed_out(job.id, "申请数据生成任务等待超时")
            return
        update_job_progress(job.id, stage="generate", progress=20, message="开始生成 Mock 数据")
        job.refresh_from_db()
        if job.status == JobStatus.CANCEL_REQUESTED:
            mark_job_cancelled(job.id)
            return
        result = execute_application_data_generation(job)
        update_job_progress(job.id, stage="persist", progress=90, message="Mock 数据生成完成")
        mark_job_success(job.id, result)
    except InvalidJobTransition:
        mark_job_cancelled(job.id)
    except SoftTimeLimitExceeded:
        mark_job_timed_out(job.id)
        raise
    except Exception as exc:
        mark_job_failed(job.id, f"{type(exc).__name__}: {exc}")
        raise
