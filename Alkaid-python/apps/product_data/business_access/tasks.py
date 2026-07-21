from celery import shared_task
from django.conf import settings

from apps.jobs.task_runner import run_menu_task
from apps.product_data.business_access.services import execute_business_access


@shared_task(
    bind=True,
    name="apps.product_data.business_access.tasks.execute_business_access",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.BUSINESS_ACCESS_TIMEOUT_SECONDS,
    time_limit=settings.BUSINESS_ACCESS_TIMEOUT_SECONDS + 10,
)
def execute_business_access_task(self, job_id: int) -> None:
    run_menu_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="业务准入任务在队列中等待超时",
        execute=execute_business_access,
    )
