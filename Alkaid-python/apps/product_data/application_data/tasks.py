from celery import shared_task
from django.conf import settings

from apps.jobs.task_runner import run_menu_task
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
    run_menu_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="申请数据生成任务等待超时",
        execute=execute_application_data_generation,
    )
