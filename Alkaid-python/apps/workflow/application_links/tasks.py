from celery import shared_task
from django.conf import settings

from apps.workflow.Jobs.integration_observer import JobIntegrationObserver
from apps.workflow.Jobs.task_runner import JobTaskContext, run_job_task

from .schemas import ApplicationLinkExecutionSnapshot
from .service import execute_application_link as execute_application_link_use_case


@shared_task(
    bind=True,
    name="apps.workflow.application_links.tasks.execute_application_link",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.APPLICATION_LINK_TIMEOUT_SECONDS,
    time_limit=settings.APPLICATION_LINK_TIMEOUT_SECONDS + 10,
)
def execute_application_link(self, job_id: int) -> None:
    def execute(context: JobTaskContext):
        snapshot = ApplicationLinkExecutionSnapshot.model_validate(
            context.job.execution_config_snapshot
        )
        context.progress(stage="validate", progress=30, message="申请链接参数校验完成")
        result = execute_application_link_use_case(
            snapshot=snapshot,
            observer=JobIntegrationObserver(context.job),
            trace_id=context.job.trace_id,
        )
        context.progress(stage="generate", progress=90, message="申请链接生成完成，正在保存结果")
        return result

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="申请链接任务在队列中等待超时",
        execute=execute,
    )
