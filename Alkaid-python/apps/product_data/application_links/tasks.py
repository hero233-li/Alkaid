import logging

from celery import shared_task
from django.conf import settings

from apps.jobs.models import Job
from apps.jobs.task_runner import JobTaskContext, run_job_task
from apps.product_data.application_links.schemas import (
    ApplicationLinkExecutionSnapshot,
    ApplicationLinkSubmission,
)
from apps.product_data.application_links.services import (
    generate_application_links,
    normalize_submission,
    resolve_execution_snapshot,
    validate_submission,
)

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
        job = context.job
        submission = ApplicationLinkSubmission.model_validate(job.payload)
        if job.execution_config_snapshot:
            snapshot = ApplicationLinkExecutionSnapshot.model_validate(
                job.execution_config_snapshot
            )
        else:
            submission = normalize_submission(submission)
            snapshot = resolve_execution_snapshot(submission)
        validate_submission(submission, snapshot)
        context.progress(stage="validate", progress=30, message="申请链接参数校验完成")
        result = generate_application_links(job, submission, snapshot=snapshot)
        context.progress(
            stage="generate",
            progress=90,
            message="申请链接生成完成，正在保存结果",
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
        },
    )
