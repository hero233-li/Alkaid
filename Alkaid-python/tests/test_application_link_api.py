import json
from unittest.mock import patch

import pytest
from django.test import Client

from apps.jobs.models import Job, JobStatus
from apps.product_data.application_links.tasks import execute_application_link


def valid_dynamic_submission() -> dict[str, object]:
    return {
        "environment": "环境1",
        "product": "产品A",
        "category": "动态链接",
        "cooperationProject": "合作项目一",
        "recommender": "张经理",
        "recommenderPhone": "13800000001",
        "loanType": "首贷",
        "customerName": "测试客户",
        "customerPhone": "13800138000",
        "customerCertificateNo": "330101199001011234",
        "customerCompanyName": "测试企业",
        "customerCompanyCode": "COMPANY-001",
    }


def valid_sun_code_submission() -> dict[str, object]:
    submission = valid_dynamic_submission()
    submission.update({"environment": "环境3", "category": "太阳码"})
    for field in (
        "customerName",
        "customerPhone",
        "customerCertificateNo",
        "customerCompanyName",
        "customerCompanyCode",
    ):
        submission.pop(field)
    return submission


@pytest.mark.django_db(transaction=True)
def test_application_link_creates_job_with_frozen_route_snapshot():
    with patch(
        "apps.product_data.application_links.views.execute_application_link.delay"
    ) as delay:
        response = Client().post(
            "/api/product-data/tools/application-links/generate",
            data=json.dumps(valid_dynamic_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="application-link-1",
            HTTP_X_TRACE_ID="link-trace-1",
        )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "pending"
    assert data["product"] == "产品A"
    assert data["executionConfigVersion"] == 1
    job = Job.objects.get(id=data["id"])
    assert job.kind == "application_link_generation"
    assert job.execution_config_snapshot == {
        "config_version": 1,
        "product": "产品A",
        "environment": "环境1",
        "category": "动态链接",
        "handler": "product_a_dynamic_link_v1",
        "required_fields": [
            "customerName",
            "customerPhone",
            "customerCertificateNo",
            "customerCompanyName",
            "customerCompanyCode",
        ],
    }
    delay.assert_called_once_with(job.id)


@pytest.mark.django_db(transaction=True)
def test_application_link_task_generates_links_and_audits_outbound_calls():
    with patch("apps.product_data.application_links.views.execute_application_link.delay"):
        response = Client().post(
            "/api/product-data/tools/application-links/generate",
            data=json.dumps(valid_dynamic_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="application-link-2",
        )
    job_id = response.json()["data"]["id"]

    execute_application_link.apply(args=[job_id], throw=True)

    job = Job.objects.get(id=job_id)
    assert job.status == JobStatus.SUCCESS
    assert job.result["links"]["applicationNo"] == "MOCK-LINK-产品A-001"
    assert job.result["links"]["internalUrl"].endswith("MOCK-LINK-产品A-001")
    assert "/dynamic/" in job.result["links"]["externalUrl"]
    assert job.api_calls.count() == 2
    assert set(job.api_calls.values_list("step", flat=True)) == {
        "application_link.create_application",
        "application_link.generate_links",
    }
    audit_body = json.dumps(list(job.api_calls.values_list("request_body", flat=True)))
    assert "13800138000" not in audit_body
    assert "330101199001011234" not in audit_body


@pytest.mark.django_db(transaction=True)
def test_application_link_uses_sun_code_handler_for_supported_route():
    with patch("apps.product_data.application_links.views.execute_application_link.delay"):
        response = Client().post(
            "/api/product-data/tools/application-links/generate",
            data=json.dumps(valid_sun_code_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="application-link-sun-code",
        )
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.execution_config_snapshot["handler"] == "product_a_sun_code_v1"

    execute_application_link.apply(args=[job.id], throw=True)

    job.refresh_from_db()
    assert job.status == JobStatus.SUCCESS
    assert "/sun-code/" in job.result["links"]["externalUrl"]


@pytest.mark.django_db
def test_application_link_rejects_unavailable_route_and_missing_dynamic_input():
    unavailable = valid_dynamic_submission()
    unavailable.update({"environment": "环境3", "category": "动态链接"})
    unavailable_response = Client().post(
        "/api/product-data/tools/application-links/generate",
        data=json.dumps(unavailable),
        content_type="application/json",
    )
    assert unavailable_response.status_code == 400
    assert "不支持该类别" in unavailable_response.json()["message"]

    incomplete = valid_dynamic_submission()
    incomplete.pop("customerCompanyCode")
    incomplete_response = Client().post(
        "/api/product-data/tools/application-links/generate",
        data=json.dumps(incomplete),
        content_type="application/json",
    )
    assert incomplete_response.status_code == 400
    assert "customerCompanyCode" in incomplete_response.json()["message"]


@pytest.mark.django_db(transaction=True)
def test_application_link_uses_its_job_snapshot_after_configuration_changes():
    with patch("apps.product_data.application_links.views.execute_application_link.delay"):
        response = Client().post(
            "/api/product-data/tools/application-links/generate",
            data=json.dumps(valid_dynamic_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="application-link-3",
        )
    job_id = response.json()["data"]["id"]

    with patch(
        "apps.product_data.application_links.tasks.resolve_execution_snapshot",
        side_effect=AssertionError("Worker must use the frozen Job snapshot"),
    ):
        execute_application_link.apply(args=[job_id], throw=True)

    assert Job.objects.get(id=job_id).status == JobStatus.SUCCESS
