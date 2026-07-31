import json

import pytest
from django.test import override_settings

from apps.jobs.models import Job, JobStatus
from apps.product_data.product_applications.tasks import execute_product_application


def _product_b_submission() -> dict[str, object]:
    return {
        "name": "产品B申请",
        "product": "product-b",
        "payload": {
            "environment": "uat1",
            "product": "product-b",
            "location": "example-location",
            "branch": "example-branch",
            "outlet": "example-outlet",
            "personName": "测试用户",
            "certificateNo": "330101199001011234",
            "cardNo": "6222000000000000",
            "phone": "13800138000",
            "customerType": "farmer",
            "applicationMethod": "normal",
            "redShieldEnabled": True,
            "idType": "01",
            "projectId": "PROJECT-001",
        },
    }


@pytest.mark.django_db
def test_readiness_checks_database_catalog_endpoints_and_messages(client) -> None:
    response = client.get("/health/ready/")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["checks"]["catalog"]["products"] == 3
    assert body["checks"]["rawMessages"]["messages"] == 1
    assert body["checks"]["agreementMessages"]["messages"] == 3


@pytest.mark.django_db
@override_settings(EXTERNAL_SYSTEM_MODE="mock", APPLICATION_LINK_URL_MODE="internal")
def test_product_application_freezes_catalog_and_reads_agreement(
    client,
    django_capture_on_commit_callbacks,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            "/api/product-data/applications",
            data=json.dumps(_product_b_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="api-product-b",
            HTTP_X_TRACE_ID="trace-api",
        )

    assert response.status_code == 202
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.status == JobStatus.SUCCESS
    assert job.execution_config_snapshot["product_code"] == "product-b"
    assert job.payload["environment"] == "UAT1"
    assert job.payload["environment"] == "UAT1"
    assert job.result["applicationLink"]["category"] == "太阳码"
    assert job.result["externalSession"]["established"] is True
    assert job.result["agreementReadCompleted"] is True
    assert job.result["agreementDocuments"][0]["fileName"] == "mock-agreement.pdf"
    assert job.api_calls.count() == 5


@pytest.mark.django_db
@override_settings(DEBUG=True, EXTERNAL_SYSTEM_MODE="mock", CELERY_TASK_ALWAYS_EAGER=False)
def test_product_application_uses_local_mock_when_broker_is_unavailable(
    client,
    monkeypatch,
    django_capture_on_commit_callbacks,
) -> None:
    def fail_enqueue(*args, **kwargs):
        raise ConnectionError("RabbitMQ is unavailable")

    monkeypatch.setattr(execute_product_application, "delay", fail_enqueue)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            "/api/product-data/applications",
            data=json.dumps(_product_b_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="api-product-b-local-fallback",
        )

    assert response.status_code == 202
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.status == JobStatus.SUCCESS
    assert job.result["agreementReadCompleted"] is True
    assert any("本地执行" in log.message for log in job.logs.all())


@pytest.mark.django_db
@override_settings(DEBUG=False, EXTERNAL_SYSTEM_MODE="real", CELERY_TASK_ALWAYS_EAGER=False)
def test_product_application_records_broker_failure_on_job(
    client,
    monkeypatch,
    django_capture_on_commit_callbacks,
) -> None:
    def fail_enqueue(*args, **kwargs):
        raise ConnectionError("RabbitMQ is unavailable")

    monkeypatch.setattr(execute_product_application, "delay", fail_enqueue)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            "/api/product-data/applications",
            data=json.dumps(_product_b_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="api-product-b-broker-failure",
        )

    assert response.status_code == 202
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.status == JobStatus.FAILED
    assert job.error_message == "任务队列不可用，请检查 RabbitMQ 和 Celery Worker"


@pytest.mark.django_db
def test_oversized_request_identifier_returns_400_before_job_creation(client) -> None:
    response = client.post(
        "/api/product-data/applications",
        data=json.dumps(_product_b_submission()),
        content_type="application/json",
        HTTP_X_IDEMPOTENCY_KEY="x" * 129,
    )

    assert response.status_code == 400
    assert Job.objects.count() == 0
