from datetime import timedelta

import pytest
from django.utils import timezone

from apps.jobs.http import sanitize
from apps.jobs.models import JobStatus
from apps.jobs.services import (
    JobConflict,
    create_job,
    mark_job_failed,
    mark_job_running,
    mark_job_timed_out,
    reconcile_expired_jobs,
    request_job_cancel,
    resolve_job_identifiers,
)


def _create_job(*, key: str = "key-1"):
    return create_job(
        kind="test",
        name="测试任务",
        product="product-a",
        payload={"value": 1},
        trace_id="trace-1",
        idempotency_key=key,
        timeout_seconds=60,
    ).job


@pytest.mark.django_db
def test_job_creation_is_idempotent_and_detects_conflicts() -> None:
    first = _create_job()
    same = create_job(
        kind="test",
        name="测试任务",
        product="product-a",
        payload={"value": 1},
        trace_id="different-trace-is-allowed",
        idempotency_key="key-1",
        timeout_seconds=60,
    )
    assert same.created is False
    assert same.job.id == first.id

    with pytest.raises(JobConflict):
        create_job(
            kind="test",
            name="其他任务",
            product="product-a",
            payload={"value": 1},
            trace_id="trace-2",
            idempotency_key="key-1",
            timeout_seconds=60,
        )


def test_request_identifiers_are_bounded_before_database_write() -> None:
    generated_key, generated_trace = resolve_job_identifiers(None, None)
    assert generated_key and generated_trace
    with pytest.raises(ValueError, match="最长"):
        resolve_job_identifiers("x" * 129, "trace")


@pytest.mark.django_db
def test_same_celery_delivery_can_resume_after_worker_loss() -> None:
    job = _create_job()
    assert mark_job_running(job.id, "task-1") is not None
    resumed = mark_job_running(job.id, "task-1")

    assert resumed is not None
    assert resumed.status == JobStatus.RUNNING
    assert mark_job_running(job.id, "other-task") is None
    assert job.logs.filter(message__contains="恢复同一任务").exists()


@pytest.mark.django_db
def test_expired_job_reconciliation_closes_active_and_cancel_requested_jobs() -> None:
    timed_out = _create_job(key="timeout")
    cancelled = _create_job(key="cancel")
    mark_job_running(cancelled.id, "task-cancel")
    request_job_cancel(cancelled.id)
    deadline = timezone.now() - timedelta(seconds=1)
    type(timed_out).objects.filter(id__in=[timed_out.id, cancelled.id]).update(deadline_at=deadline)

    result = reconcile_expired_jobs(now=timezone.now())

    timed_out.refresh_from_db()
    cancelled.refresh_from_db()
    assert result == {"cancelled": 1, "timed_out": 1}
    assert timed_out.status == JobStatus.TIMED_OUT
    assert cancelled.status == JobStatus.CANCELLED


@pytest.mark.django_db
def test_late_worker_result_does_not_overwrite_terminal_timeout() -> None:
    job = _create_job()
    mark_job_running(job.id, "task-1")
    mark_job_timed_out(job.id)
    mark_job_failed(job.id, "late failure")

    job.refresh_from_db()
    assert job.status == JobStatus.TIMED_OUT


def test_http_audit_sanitizer_masks_nested_sensitive_values() -> None:
    result = sanitize({"REQ_BODY": {"request": {"idtyNo": "1234567890", "normal": "ok"}}})
    assert result["REQ_BODY"]["request"]["idtyNo"] == "12***90"
    assert result["REQ_BODY"]["request"]["normal"] == "ok"
