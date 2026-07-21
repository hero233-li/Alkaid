import json
import logging

import pytest
from django.test import override_settings

from apps.jobs.models import Job, JobStatus
from apps.jobs.services import create_job
from apps.product_data.catalog import load_product_catalog
from apps.product_data.product_applications import services as application_services
from apps.product_data.product_applications.tasks import execute_product_application


def _product_b_submission() -> dict[str, object]:
    return {
        "name": "产品B申请",
        "product": "product-b",
        "payload": {
            "environment": "env-1",
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
        },
    }


def _application_link_submission() -> dict[str, object]:
    return {
        "env": "环境1",
        "product": "product-b",
        "category": "太阳码",
        "cooperationProjectId": "PROJECT-001",
        "payload": {"loanType": "经营贷"},
    }


def _dynamic_application_link_submission() -> dict[str, object]:
    return {
        "env": "环境1",
        "product": "product-a",
        "category": "动态链接",
        "cooperationProjectId": "PROJECT-001",
        "payload": {
            "loanType": "首贷",
            "customerName": "测试用户",
            "customerPhone": "13800138000",
            "customerCertificateNo": "330101199001011234",
            "customerCompanyName": "测试企业",
            "customerCompanyCode": "TEST-CODE",
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


@pytest.mark.django_db
@override_settings(
    EXTERNAL_SYSTEM_MODE="real",
    APPLICATION_LINK_PROTOCOL_CONFIRMED=False,
    APPLICATION_LINK_SIGNER="",
)
def test_readiness_rejects_unconfirmed_real_application_link_protocol(client) -> None:
    response = client.get("/health/ready/")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


@pytest.mark.django_db
def test_product_application_freezes_catalog_and_runs_mock_external_flow(
    client, django_capture_on_commit_callbacks
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
    assert "payload" not in response.json()["data"]
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.status == JobStatus.SUCCESS
    assert job.execution_config_snapshot["product_code"] == "product-b"
    assert job.result["applicationNo"].startswith("APP-")
    assert job.api_calls.count() == 6
    assert {"links", "application", "followup"} <= set(job.result)


@pytest.mark.django_db
def test_product_application_resumes_from_persisted_link_checkpoint(monkeypatch) -> None:
    submission = _product_b_submission()
    snapshot = load_product_catalog().snapshot("product-b")
    job = create_job(
        kind="product_application",
        name=str(submission["name"]),
        product="product-b",
        payload=submission["payload"],
        trace_id="checkpoint-trace",
        idempotency_key="checkpoint-job",
        timeout_seconds=60,
        execution_config_version=snapshot.catalog_version,
        execution_config_snapshot=snapshot.model_dump(mode="json"),
    ).job

    def fail_session(job):
        raise RuntimeError("application unavailable")

    monkeypatch.setattr(application_services, "ProductApplicationSession", fail_session)
    with pytest.raises(RuntimeError, match="application unavailable"):
        application_services.execute_product_application(job)

    job.refresh_from_db()
    assert set(job.result) == {"links"}

    def links_must_not_run_again(*args, **kwargs):
        raise AssertionError("completed links step ran again")

    monkeypatch.setattr(
        application_services,
        "generate_application_link",
        links_must_not_run_again,
    )
    with pytest.raises(RuntimeError, match="application unavailable"):
        application_services.execute_product_application(job)


@pytest.mark.django_db
@override_settings(DEBUG=True, EXTERNAL_SYSTEM_MODE="mock", CELERY_TASK_ALWAYS_EAGER=False)
def test_product_application_uses_local_mock_when_broker_is_unavailable(
    client, monkeypatch, django_capture_on_commit_callbacks
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
    assert any("本地执行" in log.message for log in job.logs.all())


@pytest.mark.django_db
@override_settings(DEBUG=False, EXTERNAL_SYSTEM_MODE="real", CELERY_TASK_ALWAYS_EAGER=False)
def test_product_application_records_broker_failure_on_job(
    client, monkeypatch, django_capture_on_commit_callbacks
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
    assert response.json()["code"] == "invalid_submission"
    assert Job.objects.count() == 0


@pytest.mark.django_db
def test_application_link_route_is_frozen_and_executes_shared_operation(
    client, caplog, django_capture_on_commit_callbacks
) -> None:
    caplog.set_level(logging.INFO)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            "/api/product-data/tools/application-links/generate",
            data=json.dumps(_application_link_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="api-link-product-b",
        )

    assert response.status_code == 202
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.status == JobStatus.SUCCESS
    assert job.execution_config_snapshot["category"] == "太阳码"
    assert job.execution_config_snapshot["environment"] == "env-1"
    assert job.execution_config_snapshot["product"] == "product-b"
    assert job.payload["env"] == "env-1"
    assert job.payload["cooperationProjectId"] == "PROJECT-001"
    assert job.result["links"]["internalUrl"].startswith("https://internal.mock.local/")
    assert job.result["links"]["externalUrl"].startswith("https://apply.mock.local/")
    assert job.api_calls.count() == 1
    events = {record.message: record for record in caplog.records}
    assert events["application_link_execution_started"].job_id == job.id
    assert events["application_link_execution_started"].product == "product-b"
    assert events["application_link_execution_started"].environment == "env-1"
    assert events["application_link_links_generated"].category == "太阳码"


@pytest.mark.django_db
def test_application_link_config_uses_stable_catalog_codes(client) -> None:
    response = client.get("/api/product-data/tools/application-links/config")

    assert response.status_code == 200
    config = response.json()["data"]
    assert config["environments"][0] == {"label": "环境1", "value": "env-1"}
    assert config["cooperationProjects"][0] == {
        "label": "合作项目一",
        "value": "PROJECT-001",
    }
    product_b = next(item for item in config["products"] if item["value"] == "product-b")
    assert product_b["label"] == "产品B"
    assert product_b["routes"][0]["environment"] == "env-1"
    assert product_b["routes"][0]["category"] == "太阳码"


@pytest.mark.django_db
def test_application_link_preserves_invalid_cooperation_project_error(client) -> None:
    submission = _application_link_submission()
    submission["cooperationProjectId"] = "UNKNOWN-PROJECT"

    response = client.post(
        "/api/product-data/tools/application-links/generate",
        data=json.dumps(submission),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "请选择有效的合作项目" in response.json()["message"]
    assert "没有该产品" not in response.json()["message"]


@pytest.mark.django_db
def test_dynamic_application_link_validates_fields_inside_request_json(
    client, django_capture_on_commit_callbacks
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            "/api/product-data/tools/application-links/generate",
            data=json.dumps(_dynamic_application_link_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="api-link-dynamic-product-a",
        )

    assert response.status_code == 202
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.status == JobStatus.SUCCESS
    assert job.api_calls.count() == 1
    assert set(job.result["links"]) == {"internalUrl", "externalUrl", "generatedAt"}
