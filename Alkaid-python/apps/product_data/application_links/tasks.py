import logging

from celery import shared_task
from django.conf import settings

from apps.jobs.models import Job
from apps.jobs.task_runner import JobTaskContext, run_job_task
from apps.product_data.application_links.flow import ApplicationLinkFlow

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="apps.product_data.application_links.tasks.execute_application_link",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.APPLICATION_LINK_TIMEOUT_SECONDS,
    time_limit=settings.APPLICATION_LINK_TIMEOUT_SECONDS + 10,
)
def execute_application_link(self, job_id: int) -> None:
    def execute(context: JobTaskContext):
        result = ApplicationLinkFlow().execute(
            job=context.job,
            progress=context.progress,
        )
        return {"links": result.model_dump(mode="json")}

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="申请链接任务在队列中等待超时",
        execute=execute,
        on_error=_log_error,
    )


def _log_error(job: Job, exc: Exception) -> None:
    del exc
    logger.exception(
        "application_link_execution_failed",
        extra={
            "job_id": job.id,
            "workflow_id": str(job.workflow_id),
            "trace_id": job.trace_id,
            "product": job.product,
            "environment": job.payload.get("env") or job.payload.get("environment"),
            "category": job.payload.get("category"),
        },
    )
