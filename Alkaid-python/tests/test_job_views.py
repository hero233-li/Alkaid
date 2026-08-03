import pytest

from apps.jobs.models import ApiCallStatus, Job, JobApiCall, JobStatus
from apps.jobs.services import add_job_log, create_job


def _job(key: str, *, name: str, product: str = "product-b") -> Job:
    return create_job(
        kind="product_application",
        name=name,
        product=product,
        payload={"secret": "not-listed"},
        trace_id=f"trace-{key}",
        idempotency_key=key,
        timeout_seconds=60,
    ).job


@pytest.mark.django_db
def test_job_list_returns_recent_jobs_and_api_call_counts(client) -> None:
    created = [_job(f"list-{index}", name=f"第 {index} 个任务") for index in range(1, 7)]
    latest = created[-1]
    JobApiCall.objects.create(
        job=latest,
        method="POST",
        url="https://service.example/customer",
        status=ApiCallStatus.SUCCESS,
    )

    first_page_response = client.get("/api/jobs/")
    second_page_response = client.get("/api/jobs/", {"page": 2})

    assert first_page_response.status_code == 200
    first_page = first_page_response.json()["data"]
    second_page = second_page_response.json()["data"]
    assert first_page["pageSize"] == 5
    assert first_page["total"] == 6
    assert first_page["totalPages"] == 2
    assert [item["id"] for item in first_page["items"]] == [
        item.id for item in reversed(created[1:])
    ]
    assert [item["id"] for item in second_page["items"]] == [created[0].id]
    assert first_page["items"][0]["apiCallCount"] == 1
    assert "apiCalls" not in first_page["items"][0]
    assert "logs" not in first_page["items"][0]
    assert "payload" not in first_page["items"][0]


@pytest.mark.django_db
def test_job_list_filters_status_and_searches_logs_and_calls(client) -> None:
    failed = _job("search-failed", name="失败任务")
    Job.objects.filter(pk=failed.pk).update(status=JobStatus.FAILED)
    add_job_log(failed, "ERROR", "客户协议查询失败", step="agreement_query")
    JobApiCall.objects.create(
        job=failed,
        method="POST",
        url="https://service.example/agreement/query",
        step="agreement.query",
        status=ApiCallStatus.FAILED,
    )
    _job("search-success", name="成功任务")

    by_log = client.get("/api/jobs/", {"status": "failed", "query": "客户协议"})
    by_call = client.get("/api/jobs/", {"query": "agreement/query"})

    assert [item["id"] for item in by_log.json()["data"]["items"]] == [failed.id]
    assert [item["id"] for item in by_call.json()["data"]["items"]] == [failed.id]


@pytest.mark.django_db
def test_job_detail_contains_logs_and_complete_internal_calls(client) -> None:
    job = _job("detail", name="详情任务")
    log = add_job_log(job, "INFO", "开始调用", step="request")
    call = JobApiCall.objects.create(
        job=job,
        celery_task_id="task-1",
        attempt=2,
        step="agreement.query",
        method="POST",
        url="https://service.example/agreement",
        request_headers={"X-Trace": "trace-detail"},
        request_body={"customer": "A"},
        response_status=200,
        response_headers={"Content-Type": "application/json"},
        response_body={"ok": True},
        duration_ms=12,
        status=ApiCallStatus.SUCCESS,
    )

    response = client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["apiCallCount"] == 1
    assert detail["logs"][-1]["id"] == log.id
    assert detail["apiCalls"] == [
        {
            "id": call.id,
            "jobId": job.id,
            "taskId": "task-1",
            "attempt": 2,
            "step": "agreement.query",
            "method": "POST",
            "url": "https://service.example/agreement",
            "requestHeaders": {"X-Trace": "trace-detail"},
            "requestBody": {"customer": "A"},
            "responseStatus": 200,
            "responseHeaders": {"Content-Type": "application/json"},
            "responseBody": {"ok": True},
            "responseTruncated": False,
            "durationMs": 12,
            "status": "success",
            "errorType": None,
            "errorMessage": None,
            "startedAt": call.started_at.isoformat(),
            "finishedAt": None,
        }
    ]
    assert "payload" not in detail

    payload_response = client.get(f"/api/jobs/{job.id}", {"includePayload": "true"})
    assert payload_response.status_code == 200
    assert payload_response.json()["data"]["payload"] == {"secret": "not-listed"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("params", "message"),
    (
        ({"status": "unknown"}, "status 参数无效"),
        ({"page": "wrong"}, "page 和 pageSize 必须是整数"),
        ({"pageSize": "101"}, "pageSize 必须在 1 到 100 之间"),
    ),
)
def test_job_list_rejects_invalid_filters(client, params, message) -> None:
    response = client.get("/api/jobs/", params)

    assert response.status_code == 400
    assert response.json()["message"] == message
