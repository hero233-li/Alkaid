from celery import shared_task
from django.conf import settings

from apps.jobs.task_runner import JobTaskContext, run_job_task
from apps.product_data.loan_status.schemas import LoanStatusOperation
from apps.product_data.loan_status.services import execute_loan_status

LOAN_STATUS_KIND_PREFIX = "loan_status."


@shared_task(
    bind=True,
    name="apps.product_data.loan_status.tasks.execute_loan_status",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.LOAN_STATUS_TIMEOUT_SECONDS,
    time_limit=settings.LOAN_STATUS_TIMEOUT_SECONDS + 10,
)
def execute_loan_status_task(self, job_id: int) -> None:
    def execute(context: JobTaskContext):
        operation = LoanStatusOperation(context.job.kind.removeprefix(LOAN_STATUS_KIND_PREFIX))
        context.progress(stage="execute", progress=35, message="贷款状态任务开始执行")
        result = execute_loan_status(context.job, operation)
        context.progress(stage="persist", progress=90, message="贷款状态处理完成")
        return result

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="贷款状态任务等待超时",
        execute=execute,
    )
