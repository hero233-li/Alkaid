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
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.services import (
    resolve_product_snapshot,
    run_product_application,
    validate_submission,
)


@shared_task(
    bind=True,
    # 保持旧名称，避免发布时遗留在消息队列中的产品申请任务无法消费。
    name="apps.product_data.tasks.execute_product_application",
    # 外系统写操作未确认幂等能力：消息领取即确认，Worker 丢失时禁止自动重放。
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS,
    time_limit=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS + 10,
)
def execute_product_application(self, job_id: int) -> None:
    task_id = str(self.request.id or "local-eager-task")
    job = mark_job_running(job_id, task_id)
    if job is None:
        return
    try:
        if job.deadline_at and job.deadline_at <= timezone.now():
            mark_job_timed_out(job.id, "任务在队列中等待时间过长，已超过截止时间")
            return
        submission = ProductApplicationSubmission(
            name=job.name,
            product=job.product,
            payload=job.payload,
        )
        execution_snapshot = resolve_product_snapshot(job, job.product)
        validate_submission(submission, execution_snapshot=execution_snapshot)
        update_job_progress(
            job.id,
            stage="validate",
            progress=40,
            message="产品申请参数校验完成",
        )
        job.refresh_from_db()
        if job.status == JobStatus.CANCEL_REQUESTED:
            mark_job_cancelled(job.id)
            return
        result = run_product_application(job, submission, snapshot=execution_snapshot)
        update_job_progress(
            job.id,
            stage="execute",
            progress=90,
            message="产品申请处理完成，正在保存结果",
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
