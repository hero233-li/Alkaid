from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from apps.jobs.models import Job, JobApiCall, JobLog, JobStatus
from apps.jobs.services import InvalidJobTransition, create_job
from apps.jobs.use_cases import cancel_job, cleanup_expired_jobs, retry_job


def _job(key: str, *, kind: str = "workflow") -> Job:
    return create_job(
        kind=kind,
        name="测试任务",
        product="",
        payload={},
        trace_id=f"trace-{key}",
        idempotency_key=key,
        timeout_seconds=60,
    ).job


@pytest.mark.django_db(transaction=True)
def test_retry_job_changes_state_and_enqueues_after_commit() -> None:
    job = _job("retry-use-case")
    Job.objects.filter(pk=job.pk).update(status=JobStatus.FAILED)
    enqueued: list[int] = []

    retried = retry_job(job.id, enqueue=lambda item: enqueued.append(item.id))

    assert retried.status == JobStatus.RETRYING
    assert retried.attempt_count == 2
    assert enqueued == [job.id]


@pytest.mark.django_db
def test_retry_job_rejects_illegal_state() -> None:
    job = _job("illegal-retry")

    with pytest.raises(InvalidJobTransition, match="不允许重试"):
        retry_job(job.id, enqueue=lambda _job: None)


@pytest.mark.django_db
def test_cancel_job_logs_revoke_failure() -> None:
    job = _job("cancel-revoke")
    Job.objects.filter(pk=job.pk).update(
        status=JobStatus.RUNNING,
        celery_task_id="celery-123",
    )

    def failing_revoke(_task_id: str) -> None:
        raise RuntimeError("broker down")

    cancelled = cancel_job(job.id, revoke=failing_revoke)

    assert cancelled.status == JobStatus.CANCEL_REQUESTED
    assert cancelled.logs.filter(level="WARN", message__contains="broker down").exists()


@pytest.mark.django_db
def test_cleanup_expired_jobs_removes_old_records_only() -> None:
    now = timezone.now()
    expired = _job("cleanup-expired")
    active = _job("cleanup-active")
    Job.objects.filter(pk=expired.pk).update(
        status=JobStatus.SUCCESS,
        expires_at=now - timedelta(seconds=1),
    )
    Job.objects.filter(pk=active.pk).update(expires_at=now + timedelta(hours=1))
    old_log = JobLog.objects.create(job=active, message="old")
    old_call = JobApiCall.objects.create(job=active, method="GET", url="https://example.test")
    cutoff_age = timedelta(hours=settings.JOB_LOG_RETENTION_HOURS + 1)
    JobLog.objects.filter(pk=old_log.pk).update(created_at=now - cutoff_age)
    JobApiCall.objects.filter(pk=old_call.pk).update(started_at=now - cutoff_age)

    counts = cleanup_expired_jobs(now=now)

    assert counts["jobs"] >= 1
    assert counts["logs"] >= 1
    assert counts["api_calls"] >= 1
    assert not Job.objects.filter(pk=expired.pk).exists()
    assert Job.objects.filter(pk=active.pk).exists()
