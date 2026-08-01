from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from apps.jobs.http import JobHttpCallObserver, format_log_value
from apps.jobs.models import Job
from apps.jobs.services import add_job_log

logger = logging.getLogger(__name__)


class JobIntegrationObserver:
    """Persist neutral integration events without leaking Job into integrations."""

    def __init__(self, job: Job) -> None:
        self._job = job
        self._handles: dict[int, tuple[JobHttpCallObserver, object]] = {}
        self._next_handle = 1

    def request_started(
        self,
        *,
        step: str,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Any,
    ) -> object:
        observer = JobHttpCallObserver(self._job, step=step)
        inner = observer.started(
            method=method,
            path=url,
            headers=headers,
            request_body=body,
        )
        handle = self._next_handle
        self._next_handle += 1
        self._handles[handle] = (observer, inner)
        return handle

    def request_finished(
        self,
        handle: object,
        *,
        status_code: int | None,
        headers: Mapping[str, str],
        body: Any,
        duration_ms: int,
        error: Exception | None,
    ) -> None:
        observer, inner = self._handles.pop(int(str(handle)))
        observer.finished(
            inner,
            status_code=status_code,
            headers=headers,
            response_body=body,
            duration_ms=duration_ms,
            error=error,
        )

    def diagnostic(
        self,
        *,
        step: str,
        title: str,
        content: Any,
        level: str = "INFO",
    ) -> None:
        message = f"{title}（敏感值已脱敏）：\n{format_log_value(content)}"
        add_job_log(
            self._job,
            level,
            message,
            step=step,
            celery_task_id=self._job.celery_task_id,
            metadata={"event": "integration_diagnostic", "title": title},
        )
        (logger.error if level == "ERROR" else logger.info)(
            "integration_diagnostic %s\n%s", title, format_log_value(content)
        )
