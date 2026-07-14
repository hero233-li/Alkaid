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
from apps.product_data.business_access.schemas import BusinessAccessOperation
from apps.product_data.business_access.services import execute_business_access

BUSINESS_ACCESS_KIND_PREFIX = "business_access."


@shared_task(
    bind=True,
    name="apps.product_data.business_access.tasks.execute_business_access",
    # 同一 Task 同时承载查询和写操作，按最保守的写操作语义禁止自动重放。
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.BUSINESS_ACCESS_TIMEOUT_SECONDS,
    time_limit=settings.BUSINESS_ACCESS_TIMEOUT_SECONDS + 10,
)
def execute_business_access_task(self, job_id: int) -> None:
    task_id = str(self.request.id or "local-eager-task")
    job = mark_job_running(job_id, task_id)
    if job is None:
        return
    try:
        if job.deadline_at and job.deadline_at <= timezone.now():
            mark_job_timed_out(job.id, "业务准入任务在队列中等待超时")
            return
        operation = BusinessAccessOperation(job.kind.removeprefix(BUSINESS_ACCESS_KIND_PREFIX))
        update_job_progress(
            job.id,
            stage="validate",
            progress=30,
            message="业务准入任务开始执行",
        )
        job.refresh_from_db()
        if job.status == JobStatus.CANCEL_REQUESTED:
            mark_job_cancelled(job.id)
            return
        result = execute_business_access(job, operation)
        update_job_progress(
            job.id,
            stage="external_call",
            progress=90,
            message="业务准入外系统处理完成，正在保存结果",
        )
        mark_job_success(job.id, result)
    except InvalidJobTransition:
        mark_job_cancelled(job.id)
    except SoftTimeLimitExceeded:
        mark_job_timed_out(job.id)
        raise
    except Exception as exc:
        mark_job_failed(job.id, f"{type(exc).__name__}: {exc}")
        raise
