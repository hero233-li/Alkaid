from datetime import timedelta

import pytest
from django.utils import timezone

from apps.jobs.http import sanitize
from apps.jobs.models import JobStatus
from apps.jobs.services import (
    InvalidJobTransition,
    JobConflict,
    create_job,
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    mark_job_timed_out,
    reconcile_expired_jobs,
    request_job_cancel,
    request_job_retry,
    resolve_job_identifiers,
)


def _create_job(*, key: str = "key-1", kind: str = "test"):
    return create_job(
        kind=kind,
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


@pytest.mark.django_db
def test_non_idempotent_external_write_job_cannot_be_retried() -> None:
    job = _create_job(key="write", kind="verification_approval.action")
    mark_job_failed(job.id, "外系统结果未知")

    with pytest.raises(InvalidJobTransition, match="禁止重试"):
        request_job_retry(job.id)


@pytest.mark.django_db
def test_running_non_idempotent_write_rejects_cancel_and_keeps_external_success(client) -> None:
    job = _create_job(key="write-cancel", kind="verification_approval.action")
    mark_job_running(job.id, "external-call-in-flight")

    response = client.post(f"/api/jobs/{job.id}/cancel")
    assert response.status_code == 409
    with pytest.raises(InvalidJobTransition, match="不能取消"):
        request_job_cancel(job.id)

    mark_job_success(job.id, {"externalWrite": "completed"})
    job.refresh_from_db()
    assert job.status == JobStatus.SUCCESS
    assert job.result == {"externalWrite": "completed"}


@pytest.mark.django_db
def test_external_write_task_rejects_cancel_during_call_and_finishes_success(
    client, monkeypatch
) -> None:
    from apps.product_data.verification_approval import tasks as verification_tasks

    job = _create_job(key="write-cancel-task", kind="verification_approval.action")

    def external_call(completing_job, operation):
        del operation
        response = client.post(f"/api/jobs/{completing_job.id}/cancel")
        assert response.status_code == 409
        return {"externalWrite": "completed"}

    monkeypatch.setattr(
        verification_tasks,
        "execute_verification_approval",
        external_call,
    )
    verification_tasks.execute_verification_approval_task.apply(
        args=(job.id,),
        throw=True,
    )

    job.refresh_from_db()
    assert job.status == JobStatus.SUCCESS
    assert job.result == {"externalWrite": "completed"}


@pytest.mark.django_db
def test_safe_query_job_can_still_be_retried() -> None:
    job = _create_job(key="query", kind="verification_approval.search")
    mark_job_failed(job.id, "查询失败")

    retried = request_job_retry(job.id)

    assert retried.status == JobStatus.RETRYING
    assert retried.attempt_count == 2


def test_external_operation_tasks_do_not_redeliver_after_worker_loss() -> None:
    from apps.product_data.application_data.tasks import execute_application_data_task
    from apps.product_data.application_links.tasks import execute_application_link
    from apps.product_data.business_access.tasks import execute_business_access_task
    from apps.product_data.card_status.tasks import execute_card_status_task
    from apps.product_data.loan_status.tasks import execute_loan_status_task
    from apps.product_data.product_applications.tasks import execute_product_application
    from apps.product_data.verification_approval.tasks import (
        execute_verification_approval_task,
    )

    tasks = (
        execute_product_application,
        execute_application_link,
        execute_business_access_task,
        execute_verification_approval_task,
        execute_application_data_task,
        execute_card_status_task,
        execute_loan_status_task,
    )
    assert all(task.acks_late is False for task in tasks)
    assert all(task.reject_on_worker_lost is False for task in tasks)


@pytest.mark.django_db
def test_job_payload_requires_staff_detail_endpoint(client, django_user_model) -> None:
    job = _create_job(key="payload-visibility")

    polling = client.get(f"/api/jobs/{job.id}")
    detail = client.get(f"/api/jobs/{job.id}?includePayload=true")
    forbidden = client.get(f"/api/jobs/{job.id}/payload")

    assert polling.status_code == 200
    assert "payload" not in polling.json()["data"]
    assert detail.status_code == 200
    assert "payload" not in detail.json()["data"]
    assert forbidden.status_code == 403

    staff = django_user_model.objects.create_user(
        username="job-auditor", password="test", is_staff=True
    )
    client.force_login(staff)
    allowed = client.get(f"/api/jobs/{job.id}/payload")
    assert allowed.json()["data"]["payload"] == {"value": 1}


def test_http_audit_sanitizer_masks_nested_sensitive_values() -> None:
    result = sanitize({"REQ_BODY": {"request": {"idtyNo": "1234567890", "normal": "ok"}}})
    assert result["REQ_BODY"]["request"]["idtyNo"] == "12***90"
    assert result["REQ_BODY"]["request"]["normal"] == "ok"
