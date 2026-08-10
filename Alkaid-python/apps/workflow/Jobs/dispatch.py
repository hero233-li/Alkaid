"""Dispatch persisted Jobs without leaking broker failures into API responses."""

import logging
from typing import Any

from django.conf import settings

from apps.workflow.Jobs.models import Job
from apps.workflow.Jobs.services import add_job_log, mark_job_failed

logger = logging.getLogger(__name__)


def enqueue_job(job: Job) -> None:
    """Enqueue one registered Job with a development-only Mock fallback."""

    task = _task_for_kind(job.kind)
    try:
        task.delay(job.id)
        return
    except Exception:  # Celery/Kombu exceptions vary by transport.
        logger.exception("job_enqueue_failed", extra={"job_id": job.id, "kind": job.kind})

    # With eager execution, delay() has already run the task. A second apply()
    # would duplicate external calls when the task itself failed.
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return

    if _allow_sync_fallback():
        add_job_log(
            job,
            "WARN",
            "消息队列不可用，开发 Mock 模式切换为本地执行",
            step="dispatch",
        )
        task.apply(args=(job.id,), throw=False)
        return

    message = "任务队列不可用，请检查 RabbitMQ 和 Celery Worker"
    mark_job_failed(job.id, message)
    add_job_log(job, "ERROR", message, step="dispatch")


def _allow_sync_fallback() -> bool:
    return bool(settings.DEBUG and settings.EXTERNAL_SYSTEM_MODE == "mock")


def _task_for_kind(kind: str) -> Any:
    if kind == "product_application":
        from apps.workflow.product_applications.tasks import execute_product_application

        return execute_product_application
    if kind == "application_link_generation":
        from apps.workflow.application_links.tasks import execute_application_link

        return execute_application_link
    raise ValueError(f"不支持的任务类型：{kind}")
