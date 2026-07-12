import json

import pytest

from apps.integrations.business_access.mock_transport import BUSINESS_ACCESS_MOCK_STORE
from apps.integrations.verification_approval.mock_transport import (
    VERIFICATION_APPROVAL_MOCK_STORE,
)
from apps.jobs.models import Job, JobStatus


@pytest.fixture(autouse=True)
def reset_external_mock_stores():
    BUSINESS_ACCESS_MOCK_STORE.reset()
    VERIFICATION_APPROVAL_MOCK_STORE.reset()


def _execute_job_request(client, capture, path: str, *, key: str, body=None) -> Job:
    with capture(execute=True):
        response = client.post(
            path,
            data=json.dumps(body) if body is not None else None,
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY=key,
            HTTP_X_TRACE_ID=f"trace-{key}",
        )
    assert response.status_code == 202
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.status == JobStatus.SUCCESS
    return job


@pytest.mark.django_db
def test_business_access_runs_search_invalidate_notifications_and_push(
    client,
    django_capture_on_commit_callbacks,
) -> None:
    config = client.get("/api/product-data/business-access/config")
    assert config.status_code == 200
    assert config.json()["data"]["environments"] == ["环境1", "环境2", "环境3"]

    search_job = _execute_job_request(
        client,
        django_capture_on_commit_callbacks,
        "/api/product-data/business-access/search",
        key="business-search",
        body={"environment": "环境1", "name": "马凡"},
    )
    records = search_job.result["records"]
    assert len(records) == 2
    assert records[0]["businessNo"].startswith("BA")
    assert search_job.api_calls.count() == 1
    record_id = records[0]["id"]

    invalidate_job = _execute_job_request(
        client,
        django_capture_on_commit_callbacks,
        f"/api/product-data/business-access/{record_id}/invalidate",
        key="business-invalidate",
    )
    assert invalidate_job.result["record"]["status"] == "invalid"

    notifications_job = _execute_job_request(
        client,
        django_capture_on_commit_callbacks,
        f"/api/product-data/business-access/{record_id}/notifications/query",
        key="business-notifications",
    )
    notifications = notifications_job.result["notifications"]
    assert len(notifications) == 2

    push_job = _execute_job_request(
        client,
        django_capture_on_commit_callbacks,
        (
            f"/api/product-data/business-access/{record_id}/notifications/"
            f"{notifications[0]['id']}/push-new"
        ),
        key="business-push",
    )
    assert push_job.result["pushResult"]["versionType"] == "latest"
    assert "已推送" in push_job.result["pushResult"]["message"]


@pytest.mark.django_db
def test_verification_approval_data_and_mutations_come_from_backend(client) -> None:
    config = client.get("/api/product-data/verification-approval/config")
    assert config.status_code == 200
    assert config.json()["data"]["categories"] == ["合同核实", "资料核实", "放款核实"]

    search = client.post(
        "/api/product-data/verification-approval/search",
        data=json.dumps(
            {
                "environment": "环境1",
                "category": "合同核实",
                "contractNo": "HT20260710001",
            }
        ),
        content_type="application/json",
        HTTP_X_TRACE_ID="verify-search",
    )
    assert search.status_code == 200
    task = search.json()["data"]
    assert task["ownershipStatus"] == "unclaimed"
    assert len(task["items"]) == 6

    claim = client.post(
        f"/api/product-data/verification-approval/{task['id']}/claim",
        content_type="application/json",
    )
    assert claim.status_code == 200
    assert claim.json()["data"]["ownershipStatus"] == "claimed"

    item = client.post(
        f"/api/product-data/verification-approval/{task['id']}/items/identity",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
    )
    assert item.status_code == 200
    assert item.json()["data"]["items"][0]["status"] == "completed"

    complete = client.post(
        f"/api/product-data/verification-approval/{task['id']}/actions/complete",
        content_type="application/json",
    )
    assert complete.status_code == 200
    assert all(value["status"] == "completed" for value in complete.json()["data"]["items"])

    submit = client.post(
        f"/api/product-data/verification-approval/{task['id']}/actions/submit",
        content_type="application/json",
    )
    assert submit.status_code == 200
    assert submit.json()["data"]["taskStatus"] == "已提交"


@pytest.mark.django_db
def test_verification_search_can_return_no_external_task(client) -> None:
    response = client.post(
        "/api/product-data/verification-approval/search",
        data=json.dumps({"environment": "环境1", "category": "资料核实", "contractNo": "0"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["data"] is None
