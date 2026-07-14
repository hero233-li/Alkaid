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
from apps.product_data.card_status.schemas import CardStatusOperation
from apps.product_data.card_status.services import execute_card_status

CARD_STATUS_KIND_PREFIX = "card_status."


@shared_task(
    bind=True,
    name="apps.product_data.card_status.tasks.execute_card_status",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.CARD_STATUS_TIMEOUT_SECONDS,
    time_limit=settings.CARD_STATUS_TIMEOUT_SECONDS + 10,
)
def execute_card_status_task(self, job_id: int) -> None:
    job = mark_job_running(job_id, str(self.request.id or "local-eager-task"))
    if job is None:
        return
    try:
        if job.deadline_at and job.deadline_at <= timezone.now():
            mark_job_timed_out(job.id, "卡状态任务等待超时")
            return
        operation = CardStatusOperation(job.kind.removeprefix(CARD_STATUS_KIND_PREFIX))
        update_job_progress(job.id, stage="execute", progress=35, message="卡状态任务开始执行")
        job.refresh_from_db()
        if job.status == JobStatus.CANCEL_REQUESTED:
            mark_job_cancelled(job.id)
            return
        result = execute_card_status(job, operation)
        update_job_progress(job.id, stage="persist", progress=90, message="卡状态处理完成")
        mark_job_success(job.id, result)
    except InvalidJobTransition:
        mark_job_cancelled(job.id)
    except SoftTimeLimitExceeded:
        mark_job_timed_out(job.id)
        raise
    except Exception as exc:
        mark_job_failed(job.id, f"{type(exc).__name__}: {exc}")
        raise
