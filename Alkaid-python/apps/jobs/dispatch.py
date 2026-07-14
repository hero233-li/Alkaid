"""Dispatch persisted Jobs without leaking broker failures into API responses."""

import logging
from typing import Any

from django.conf import settings

from apps.jobs.models import Job
from apps.jobs.services import add_job_log, mark_job_failed

logger = logging.getLogger(__name__)


def enqueue_job(job: Job) -> None:
    """Enqueue a Job, with a development-only fallback for local Mock mode.

    A job is persisted before this function is called.  If RabbitMQ is down,
    production keeps that fact on the Job instead of turning the HTTP response
    into an unhelpful HTML 500.  Local Mock development can still be used
    without installing RabbitMQ: the task is executed synchronously in the
    request process and the normal Job state machine remains authoritative.
    """

    task = _task_for_kind(job.kind)
    try:
        task.delay(job.id)
        return
    except Exception:  # Celery/Kombu exceptions vary by transport.
        logger.exception("job_enqueue_failed", extra={"job_id": job.id, "kind": job.kind})

    # With Celery eager execution, delay() has already run the task.  A second
    # apply() would duplicate external calls when the task itself failed.
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return

    if _allow_sync_fallback():
        add_job_log(
            job,
            "WARN",
            "消息队列不可用，开发 Mock 模式切换为本地执行",
            step="dispatch",
        )
        # throw=False keeps a business/external failure in the Job record and
        # prevents it from becoming a second HTTP 500.
        task.apply(args=(job.id,), throw=False)
        return

    message = "任务队列不可用，请检查 RabbitMQ 和 Celery Worker"
    mark_job_failed(job.id, message)
    add_job_log(job, "ERROR", message, step="dispatch")


def _allow_sync_fallback() -> bool:
    return bool(settings.DEBUG and settings.EXTERNAL_SYSTEM_MODE == "mock")


def _task_for_kind(kind: str) -> Any:
    if kind == "product_application":
        from apps.product_data.product_applications.tasks import execute_product_application

        return execute_product_application
    if kind == "application_link_generation":
        from apps.product_data.application_links.tasks import execute_application_link

        return execute_application_link
    if kind.startswith("business_access."):
        from apps.product_data.business_access.tasks import execute_business_access_task

        return execute_business_access_task
    if kind.startswith("verification_approval."):
        from apps.product_data.verification_approval.tasks import (
            execute_verification_approval_task,
        )

        return execute_verification_approval_task
    if kind == "application_data.generate":
        from apps.product_data.application_data.tasks import execute_application_data_task

        return execute_application_data_task
    if kind.startswith("card_status."):
        from apps.product_data.card_status.tasks import execute_card_status_task

        return execute_card_status_task
    if kind.startswith("loan_status."):
        from apps.product_data.loan_status.tasks import execute_loan_status_task

        return execute_loan_status_task
    raise ValueError(f"不支持的任务类型：{kind}")
