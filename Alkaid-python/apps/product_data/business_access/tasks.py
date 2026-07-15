from celery import shared_task
from django.conf import settings

from apps.jobs.task_runner import JobTaskContext, run_job_task
from apps.product_data.business_access.schemas import BusinessAccessOperation
from apps.product_data.business_access.services import execute_business_access

BUSINESS_ACCESS_KIND_PREFIX = "business_access."


@shared_task(
    bind=True,
    name="apps.product_data.business_access.tasks.execute_business_access",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.BUSINESS_ACCESS_TIMEOUT_SECONDS,
    time_limit=settings.BUSINESS_ACCESS_TIMEOUT_SECONDS + 10,
)
def execute_business_access_task(self, job_id: int) -> None:
    def execute(context: JobTaskContext):
        operation = BusinessAccessOperation(
            context.job.kind.removeprefix(BUSINESS_ACCESS_KIND_PREFIX)
        )
        context.progress(stage="validate", progress=30, message="业务准入任务开始执行")
        result = execute_business_access(context.job, operation)
        context.progress(
            stage="external_call",
            progress=90,
            message="业务准入外系统处理完成，正在保存结果",
        )
        return result

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="业务准入任务在队列中等待超时",
        execute=execute,
    )
