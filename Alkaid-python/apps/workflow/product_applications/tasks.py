from celery import shared_task
from django.conf import settings

from apps.utils.http import config as cjdk_config
from apps.workflow.Jobs.integration_observer import JobIntegrationObserver
from apps.workflow.Jobs.services import add_business_log
from apps.workflow.Jobs.task_runner import JobTaskContext, run_job_task
from apps.workflow.product_applications.cjdk.runtime import ProductApplicationRuntime
from apps.workflow.product_applications.schemas import ProductApplicationSubmission
from apps.workflow.product_applications.workflow import (
    execute_product_application as execute_product_application_use_case,
)
from apps.workflow.product_applications.workflow import resolve_product_snapshot


@shared_task(
    bind=True,
    name="apps.workflow.product_applications.tasks.execute_product_application",
    acks_late=False,
    reject_on_worker_lost=False,
    soft_time_limit=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS,
    time_limit=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS + 10,
)
def execute_product_application(self, job_id: int) -> None:
    business_messages = {
        "validate": "申请资料校验完成",
        "application_link": "申请入口生成完成",
        "session": "申请环境准备完成",
        "agreement_read": "申请协议准备完成",
        "application_submit": "产品申请提交完成",
        "identity_verify": "身份认证完成",
    }

    def execute(context: JobTaskContext):
        add_business_log(
            context.job,
            "开始处理产品申请",
            step="started",
            progress=10,
        )

        def report(*, stage: str, progress: int, message: str) -> None:
            context.progress(stage=stage, progress=progress, message=message)
            business_message = business_messages.get(stage)
            if business_message:
                context.job.refresh_from_db()
                add_business_log(
                    context.job,
                    business_message,
                    step=stage,
                    progress=progress,
                )

        snapshot = resolve_product_snapshot(context.job, context.job.product)
        submission = ProductApplicationSubmission(
            name=context.job.name,
            product=snapshot.product_code,
            payload=dict(snapshot.normalized_payload),
        )
        integration_settings = cjdk_config.get_cjdk_jyrc_settings()
        observer = JobIntegrationObserver(context.job)
        runtime = ProductApplicationRuntime(
            settings=integration_settings,
            observer=observer,
            trace_id=context.job.trace_id,
            environment=snapshot.environment,
        )
        result = execute_product_application_use_case(
            runtime=runtime,
            submission=submission,
            snapshot=snapshot,
            application_link_kind=integration_settings.application_link_url_mode,
            progress=report,
        )
        context.job.refresh_from_db()
        add_business_log(
            context.job,
            "产品申请办理完成",
            step="completed",
            progress=100,
        )
        return result

    def on_error(job, _error: Exception) -> None:
        job.refresh_from_db()
        add_business_log(
            job,
            "产品申请处理失败，请前往任务中心查看技术详情",
            step="failed",
            level="ERROR",
            progress=100,
        )

    run_job_task(
        job_id=job_id,
        celery_task_id=str(self.request.id or "local-eager-task"),
        queue_timeout_message="任务在队列中等待时间过长，已超过截止时间",
        execute=execute,
        on_error=on_error,
    )
