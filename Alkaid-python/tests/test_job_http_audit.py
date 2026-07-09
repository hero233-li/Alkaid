import httpx
import pytest
from pydantic import BaseModel

from apps.integrations.http import HttpClient, HttpClientConfig
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import JobApiCall
from apps.jobs.services import JobRepository


class SensitiveRequest(BaseModel):
    certificateNo: str


class SensitiveResponse(BaseModel):
    cardNo: str
    result: str


@pytest.mark.django_db(transaction=True)
def test_http_call_audit_records_response_and_masks_sensitive_values():
    created = JobRepository.create(
        kind="test",
        name="审计测试",
        product="",
        payload={},
        trace_id="trace-http",
        idempotency_key="http-audit-1",
        timeout_seconds=30,
    )
    job = created.job
    job.celery_task_id = "celery-task-1"
    job.save(update_fields=["celery_task_id"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"cardNo": "6222020012345678", "result": "ok"},
        )

    with HttpClient(
        HttpClientConfig(base_url="https://example.test", token="secret-token", max_retries=0),
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.request(
            "POST",
            "/v1/applications",
            response_model=SensitiveResponse,
            body=SensitiveRequest(certificateNo="330101199001011234"),
            workflow_id="trace-http",
            observer=JobHttpCallObserver(job, step="submit_application"),
        )

    assert result.result == "ok"
    call = JobApiCall.objects.get(job=job)
    assert call.status == "success"
    assert call.response_status == 200
    assert call.request_headers["authorization"] != "Bearer secret-token"
    assert call.request_body["body"]["certificateNo"] != "330101199001011234"
    assert call.response_body["cardNo"] != "6222020012345678"
    assert call.duration_ms is not None

    messages = list(job.logs.values_list("message", flat=True))
    assert any("请求外部接口" in message for message in messages)
    assert any("外部接口成功" in message for message in messages)
