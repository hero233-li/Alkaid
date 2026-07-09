from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from apps.jobs.models import JobStatus
from apps.jobs.services import InvalidJobTransition, JobRepository
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.services import (
    ProductApplicationExecutor,
    validate_submission,
)


@shared_task(
    bind=True,
    # 保持旧名称，避免发布时遗留在消息队列中的产品申请任务无法消费。
    name="apps.product_data.tasks.execute_product_application",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS,
    time_limit=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS + 10,
)
def execute_product_application(self, job_id: int) -> None:
    task_id = str(self.request.id or "local-eager-task")
    job = JobRepository.mark_running(job_id, task_id)
    if job is None:
        return
    try:
        if job.deadline_at and job.deadline_at <= timezone.now():
            JobRepository.mark_timed_out(job.id, "任务在队列中等待时间过长，已超过截止时间")
            return
        submission = ProductApplicationSubmission(
            name=job.name,
            product=job.product,
            payload=job.payload,
        )
        execution_snapshot = ProductApplicationExecutor.resolve_snapshot(job, job.product)
        validate_submission(submission, execution_snapshot=execution_snapshot)
        JobRepository.update_progress(
            job.id,
            stage="validate",
            progress=40,
            message="产品申请参数校验完成",
        )
        job.refresh_from_db()
        if job.status == JobStatus.CANCEL_REQUESTED:
            JobRepository.mark_cancelled(job.id)
            return
        result = ProductApplicationExecutor().execute(job, submission, snapshot=execution_snapshot)
        JobRepository.update_progress(
            job.id,
            stage="execute",
            progress=90,
            message="产品申请处理完成，正在保存结果",
        )
        JobRepository.mark_success(job.id, result)
    except InvalidJobTransition:
        JobRepository.mark_cancelled(job.id)
    except SoftTimeLimitExceeded:
        JobRepository.mark_timed_out(job.id)
        raise
    except Exception as exc:
        JobRepository.mark_failed(job.id, f"{type(exc).__name__}: {exc}")
        raise
