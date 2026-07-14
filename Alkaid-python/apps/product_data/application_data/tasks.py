from celery import shared_task
from django.conf import settings

from apps.jobs.task_runner import JobTaskContext, run_job_task
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
    def execute(context: JobTaskContext):
        context.progress(stage="generate", progress=20, message="开始生成 Mock 数据")
        result = execute_application_data_generation(context.job)
        context.progress(stage="persist", progress=90, message="Mock 数据生成完成")
        return result

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="申请数据生成任务等待超时",
        execute=execute,
    )
