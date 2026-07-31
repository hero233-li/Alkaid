from celery import shared_task
from django.conf import settings

from apps.jobs.task_runner import JobTaskContext, run_job_task
from apps.product_data.product_applications.flow import ProductApplicationFlow


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
        return ProductApplicationFlow().execute(
            job=context.job,
            progress=context.progress,
        )

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="任务在队列中等待时间过长，已超过截止时间",
        execute=execute,
    )
