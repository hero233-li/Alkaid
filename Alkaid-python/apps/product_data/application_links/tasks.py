from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from apps.jobs.models import JobStatus
from apps.jobs.services import (
    InvalidJobTransition,
    mark_job_cancelled,
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    mark_job_timed_out,
    update_job_progress,
)
from apps.product_data.application_links.schemas import (
    ApplicationLinkExecutionSnapshot,
    ApplicationLinkSubmission,
)
from apps.product_data.application_links.services import (
    generate_application_links,
    resolve_execution_snapshot,
    validate_submission,
)


@shared_task(
    bind=True,
    name="apps.product_data.application_links.tasks.execute_application_link",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=settings.APPLICATION_LINK_TIMEOUT_SECONDS,
    time_limit=settings.APPLICATION_LINK_TIMEOUT_SECONDS + 10,
)
def execute_application_link(self, job_id: int) -> None:
    task_id = str(self.request.id or "local-eager-task")
    job = mark_job_running(job_id, task_id)
    if job is None:
        return
    try:
        if job.deadline_at and job.deadline_at <= timezone.now():
            mark_job_timed_out(job.id, "申请链接任务在队列中等待超时")
            return
        submission = ApplicationLinkSubmission.model_validate(job.payload)
        snapshot = (
            ApplicationLinkExecutionSnapshot.model_validate(job.execution_config_snapshot)
            if job.execution_config_snapshot
            else resolve_execution_snapshot(submission)
        )
        validate_submission(submission, snapshot)
        update_job_progress(
            job.id,
            stage="validate",
            progress=30,
            message="申请链接参数校验完成",
        )
        job.refresh_from_db()
        if job.status == JobStatus.CANCEL_REQUESTED:
            mark_job_cancelled(job.id)
            return
        result = generate_application_links(job, submission, snapshot=snapshot)
        update_job_progress(
            job.id,
            stage="generate",
            progress=90,
            message="申请链接生成完成，正在保存结果",
        )
        mark_job_success(job.id, {"links": result.model_dump(mode="json")})
    except InvalidJobTransition:
        mark_job_cancelled(job.id)
    except SoftTimeLimitExceeded:
        mark_job_timed_out(job.id)
        raise
    except Exception as exc:
        mark_job_failed(job.id, f"{type(exc).__name__}: {exc}")
        raise
