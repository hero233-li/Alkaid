from celery import shared_task
from django.conf import settings

from apps.integrations.cjdk_jyrc import config as cjdk_config
from apps.integrations.cjdk_jyrc.runtime import CjdkJyrcRuntime
from apps.jobs.integration_observer import JobIntegrationObserver
from apps.jobs.task_runner import JobTaskContext, run_job_task
from apps.product_data.product_applications.preparation import resolve_product_snapshot
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.use_cases import (
    execute_product_application as execute_product_application_use_case,
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
        snapshot = resolve_product_snapshot(context.job, context.job.product)
        submission = ProductApplicationSubmission(
            name=context.job.name,
            product=snapshot.product_code,
            payload=dict(snapshot.normalized_payload),
        )
        integration_settings = cjdk_config.get_cjdk_jyrc_settings()
        observer = JobIntegrationObserver(context.job)
        runtime = CjdkJyrcRuntime(
            settings=integration_settings,
            observer=observer,
            trace_id=context.job.trace_id,
            environment=snapshot.environment,
        )
        return execute_product_application_use_case(
            runtime=runtime,
            application_links=runtime.application_links,
            external_session=runtime.external_session,
            agreements=runtime.agreements,
            submission=submission,
            snapshot=snapshot,
            application_link_kind=integration_settings.application_link_url_mode,
            progress=context.progress,
        )

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="任务在队列中等待时间过长，已超过截止时间",
        execute=execute,
    )
