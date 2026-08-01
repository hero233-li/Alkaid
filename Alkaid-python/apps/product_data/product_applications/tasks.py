from celery import shared_task
from django.conf import settings

from apps.integrations.cjdk_jyrc import config as cjdk_config
from apps.integrations.cjdk_jyrc.adapter import CjdkJyrcAdapter
from apps.jobs.integration_observer import JobIntegrationObserver
from apps.jobs.task_runner import JobTaskContext, run_job_task
from apps.product_data.product_applications.flow import ProductApplicationFlow
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.services import resolve_product_snapshot


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
        snapshot = resolve_product_snapshot(context.job, context.job.product)
        submission = ProductApplicationSubmission(
            name=context.job.name,
            product=snapshot.product_code,
            payload=dict(snapshot.normalized_payload),
        )
        integration_settings = cjdk_config.get_cjdk_jyrc_settings()
        observer = JobIntegrationObserver(context.job)
        adapter = CjdkJyrcAdapter(
            settings=integration_settings,
            observer=observer,
            trace_id=context.job.trace_id,
            environment=snapshot.environment,
        )
        return ProductApplicationFlow(adapter).execute(
            job_id=context.job.id,
            trace_id=context.job.trace_id,
            submission=submission,
            snapshot=snapshot,
            progress=context.progress,
        )

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="任务在队列中等待时间过长，已超过截止时间",
        execute=execute,
    )
