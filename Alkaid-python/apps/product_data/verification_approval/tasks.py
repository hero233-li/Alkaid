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
from apps.product_data.verification_approval.schemas import VerificationOperation
from apps.product_data.verification_approval.services import execute_verification_approval

VERIFICATION_APPROVAL_KIND_PREFIX = "verification_approval."


@shared_task(
    bind=True,
    name="apps.product_data.verification_approval.tasks.execute_verification_approval",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=settings.VERIFICATION_APPROVAL_TIMEOUT_SECONDS,
    time_limit=settings.VERIFICATION_APPROVAL_TIMEOUT_SECONDS + 10,
)
def execute_verification_approval_task(self, job_id: int) -> None:
    task_id = str(self.request.id or "local-eager-task")
    job = mark_job_running(job_id, task_id)
    if job is None:
        return
    try:
        if job.deadline_at and job.deadline_at <= timezone.now():
            mark_job_timed_out(job.id, "核实审批任务在队列中等待超时")
            return
        operation = VerificationOperation(
            job.kind.removeprefix(VERIFICATION_APPROVAL_KIND_PREFIX)
        )
        update_job_progress(
            job.id,
            stage="validate",
            progress=30,
            message="核实审批任务开始执行",
        )
        job.refresh_from_db()
        if job.status == JobStatus.CANCEL_REQUESTED:
            mark_job_cancelled(job.id)
            return
        result = execute_verification_approval(job, operation)
        update_job_progress(
            job.id,
            stage="external_call",
            progress=90,
            message="核实审批外系统处理完成，正在保存结果",
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
