from celery import shared_task
from django.conf import settings

from apps.jobs.task_runner import JobTaskContext, run_job_task
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
    def execute(context: JobTaskContext):
        operation = CardStatusOperation(context.job.kind.removeprefix(CARD_STATUS_KIND_PREFIX))
        context.progress(stage="execute", progress=35, message="卡状态任务开始执行")
        result = execute_card_status(context.job, operation)
        context.progress(stage="persist", progress=90, message="卡状态处理完成")
        return result

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="卡状态任务等待超时",
        execute=execute,
    )
