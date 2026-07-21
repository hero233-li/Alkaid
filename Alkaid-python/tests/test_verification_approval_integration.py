import json

import httpx
import pytest

import apps.integrations.product_system.verification_approval as verification_module
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.jobs.models import ApiCallStatus, Job, JobStatus
from apps.jobs.services import create_job, mark_job_success
from apps.product_data.verification_approval.services import _context_digest


def _client(handler) -> HttpClient:
    return HttpClient(
        HttpClientConfig(
            base_url="https://verification-approval.example",
            max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )


def _submit_search(client, capture, *, key: str) -> Job:
    with capture(execute=True):
        response = client.post(
            "/api/product-data/verification-approval/search",
            data=json.dumps(
                {
                    "environment": "环境1",
                    "category": "合同核实",
                    "contractNo": "HT-FAILURE",
                }
            ),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY=key,
        )
    assert response.status_code == 202
    return Job.objects.get(id=response.json()["data"]["id"])


def _submit_action(client, capture, *, key: str) -> Job:
    task = {
        "id": "VERIFY-FAILURE",
        "contractNo": "HT-FAILURE",
        "ownershipStatus": "claimed",
        "taskStatus": "待核实",
        "node": "核实",
        "tellerNo": "T1",
        "organizationNo": "ORG1",
        "productName": "产品 B",
        "items": [{"id": "identity", "title": "身份核实", "status": "completed"}],
    }
    source = create_job(
        kind="verification_approval",
        name="核实审批上下文",
        product="产品数据",
        payload={"operation": "search"},
        trace_id=f"{key}-source-trace",
        idempotency_key=f"{key}-source",
        timeout_seconds=30,
    ).job
    proof = {
        "sourceJobId": source.id,
        "version": 1,
        "digest": _context_digest(source.id, 1, task),
    }
    mark_job_success(source.id, {"task": task, "contextProof": proof})

    with capture(execute=True):
        response = client.post(
            "/api/product-data/verification-approval/VERIFY-FAILURE/actions/submit",
            data=json.dumps({"action": "submit", "context": task, "contextProof": proof}),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY=key,
        )
    assert response.status_code == 202
    return Job.objects.get(id=response.json()["data"]["id"])


@pytest.mark.django_db
def test_verification_http_failure_marks_job_and_api_call_failed(
    client,
    monkeypatch,
    django_capture_on_commit_callbacks,
) -> None:
    monkeypatch.setattr(
        verification_module,
        "create_product_system_client",
        lambda service: _client(lambda request: httpx.Response(503, json={"message": "down"})),
    )

    job = _submit_search(
        client,
        django_capture_on_commit_callbacks,
        key="verification-http-failure",
    )

    assert job.status == JobStatus.FAILED
    call = job.api_calls.get()
    assert call.status == ApiCallStatus.FAILED
    assert call.response_status == 503
    assert call.error_type == "ExternalServiceError"


@pytest.mark.django_db
def test_verification_business_failure_marks_job_and_api_call_failed(
    client,
    monkeypatch,
    django_capture_on_commit_callbacks,
) -> None:
    monkeypatch.setattr(
        verification_module,
        "create_product_system_client",
        lambda service: _client(
            lambda request: httpx.Response(
                200,
                json={"code": "9999", "message": "rejected", "data": None},
            )
        ),
    )

    job = _submit_search(
        client,
        django_capture_on_commit_callbacks,
        key="verification-business-failure",
    )

    assert job.status == JobStatus.FAILED
    call = job.api_calls.get()
    assert call.status == ApiCallStatus.FAILED
    assert call.response_status == 200
    assert call.error_type == "BusinessResponseError"
    assert call.response_body["code"] == "9999"


@pytest.mark.django_db
def test_verification_mutation_failure_is_audited_and_not_reported_successful(
    client,
    monkeypatch,
    django_capture_on_commit_callbacks,
) -> None:
    monkeypatch.setattr(
        verification_module,
        "create_product_system_client",
        lambda service: _client(
            lambda request: httpx.Response(
                200,
                json={"code": "9999", "message": "submit rejected", "data": None},
            )
        ),
    )

    job = _submit_action(
        client,
        django_capture_on_commit_callbacks,
        key="verification-action-failure",
    )

    assert job.status == JobStatus.FAILED
    assert job.kind == "verification_approval"
    call = job.api_calls.get()
    assert call.step == "verification_approval.action"
    assert call.status == ApiCallStatus.FAILED
    assert call.error_type == "BusinessResponseError"
