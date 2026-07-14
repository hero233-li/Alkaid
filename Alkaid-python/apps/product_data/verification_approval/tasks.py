from celery import shared_task
from django.conf import settings

from apps.jobs.task_runner import JobTaskContext, run_job_task
from apps.product_data.verification_approval.schemas import VerificationOperation
from apps.product_data.verification_approval.services import execute_verification_approval

VERIFICATION_APPROVAL_KIND_PREFIX = "verification_approval."


@shared_task(
    bind=True,
    name="apps.product_data.verification_approval.tasks.execute_verification_approval",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.VERIFICATION_APPROVAL_TIMEOUT_SECONDS,
    time_limit=settings.VERIFICATION_APPROVAL_TIMEOUT_SECONDS + 10,
)
def execute_verification_approval_task(self, job_id: int) -> None:
    def execute(context: JobTaskContext):
        operation = VerificationOperation(
            context.job.kind.removeprefix(VERIFICATION_APPROVAL_KIND_PREFIX)
        )
        context.progress(stage="validate", progress=30, message="核实审批任务开始执行")
        result = execute_verification_approval(context.job, operation)
        context.progress(
            stage="external_call",
            progress=90,
            message="核实审批外系统处理完成，正在保存结果",
        )
        return result

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="核实审批任务在队列中等待超时",
        execute=execute,
    )
