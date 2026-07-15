from celery import shared_task
from django.conf import settings

from apps.jobs.task_runner import JobTaskContext, run_job_task
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.services import (
    resolve_product_snapshot,
    run_product_application,
    validate_submission,
)


@shared_task(
    bind=True,
    name="apps.product_data.tasks.execute_product_application",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS,
    time_limit=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS + 10,
)
def execute_product_application(self, job_id: int) -> None:
    def execute(context: JobTaskContext):
        job = context.job
        submission = ProductApplicationSubmission(
            name=job.name,
            product=job.product,
            payload=job.payload,
        )
        execution_snapshot = resolve_product_snapshot(job, job.product)
        validate_submission(submission, execution_snapshot=execution_snapshot)
        context.progress(stage="validate", progress=40, message="产品申请参数校验完成")
        result = run_product_application(job, submission, snapshot=execution_snapshot)
        context.progress(
            stage="execute",
            progress=90,
            message="产品申请处理完成，正在保存结果",
        )
        return result

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="任务在队列中等待时间过长，已超过截止时间",
        execute=execute,
    )
