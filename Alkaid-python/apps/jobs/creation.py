import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.errors import InvalidSubmission
from apps.jobs.errors import JobConflict
from apps.jobs.job_logs import add_job_log
from apps.jobs.models import Job

MAX_REQUEST_IDENTIFIER_LENGTH = 128


@dataclass(frozen=True)
class CreatedJob:
    job: Job
    created: bool


def resolve_job_identifiers(
    idempotency_key: str | None,
    trace_id: str | None,
) -> tuple[str, str]:
    resolved_idempotency_key = (idempotency_key or str(uuid.uuid4())).strip()
    resolved_trace_id = (trace_id or str(uuid.uuid4())).strip()
    for label, value in (
        ("X-Idempotency-Key", resolved_idempotency_key),
        ("X-Trace-ID", resolved_trace_id),
    ):
        if not value:
            raise InvalidSubmission(f"{label} 不能为空")
        if len(value) > MAX_REQUEST_IDENTIFIER_LENGTH:
            raise InvalidSubmission(f"{label} 最长为 {MAX_REQUEST_IDENTIFIER_LENGTH} 个字符")
    return resolved_idempotency_key, resolved_trace_id


def create_job(
    *,
    kind: str,
    name: str,
    product: str,
    payload: dict[str, Any],
    trace_id: str,
    idempotency_key: str,
    timeout_seconds: int,
    execution_config_version: int = 1,
    execution_config_snapshot: dict[str, Any] | None = None,
) -> CreatedJob:
    idempotency_key, trace_id = resolve_job_identifiers(idempotency_key, trace_id)
    if timeout_seconds <= 0:
        raise InvalidSubmission("任务超时时间必须大于 0")
    now = timezone.now()
    try:
        with transaction.atomic():
            job = Job.objects.create(
                kind=kind,
                name=name,
                product=product,
                payload=payload,
                trace_id=trace_id,
                idempotency_key=idempotency_key,
                timeout_seconds=timeout_seconds,
                execution_config_version=execution_config_version,
                execution_config_snapshot=execution_config_snapshot or {},
                deadline_at=now + timedelta(seconds=timeout_seconds),
                expires_at=now + timedelta(hours=settings.JOB_RETENTION_HOURS),
            )
            add_job_log(job, "INFO", "任务已创建，等待执行", step="created")
            return CreatedJob(job=job, created=True)
    except IntegrityError as exc:
        try:
            job = Job.objects.get(idempotency_key=idempotency_key)
        except Job.DoesNotExist:
            raise exc from None
        if job.kind != kind or job.name != name or job.product != product or job.payload != payload:
            raise JobConflict("幂等键已被其他请求使用") from None
        return CreatedJob(job=job, created=False)
