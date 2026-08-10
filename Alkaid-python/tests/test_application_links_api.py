import json

import pytest
from django.test import override_settings

from apps.workflow.Jobs.models import Job, JobStatus


def test_application_link_config_comes_from_product_catalog(client) -> None:
    response = client.get("/api/product-data/tools/application-links/config")

    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["value"] for item in data["environments"]] == ["UAT1", "UAT2", "UATC"]
    product_b = next(item for item in data["products"] if item["value"] == "product-b")
    assert {
        "environment": "UAT1",
        "category": "太阳码",
        "requiredFields": ["cooperationProjectId"],
    } in product_b["routes"]
    assert {item["value"] for item in data["cooperationProjects"]} == {
        "PROJECT-001",
        "PROJECT-002",
        "PROJECT-003",
    }


@pytest.mark.django_db
@override_settings(EXTERNAL_SYSTEM_MODE="mock")
def test_application_link_generation_reuses_java_gateway_flow(
    client,
    django_capture_on_commit_callbacks,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            "/api/product-data/tools/application-links/generate",
            data=json.dumps(
                {
                    "env": "uat1",
                    "product": "product-b",
                    "category": "太阳码",
                    "cooperationProjectId": "PROJECT-002",
                    "payload": {"loanType": "首贷"},
                }
            ),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="application-link-api-success",
            HTTP_X_TRACE_ID="application-link-trace",
        )

    assert response.status_code == 202
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.kind == "application_link_generation"
    assert job.status == JobStatus.SUCCESS
    assert job.execution_config_snapshot["route"]["category_code"] == "SUN_CODE"
    assert job.result["links"]["internalUrl"].startswith(
        "https://cjdk-jyrc.mock/application-entry/"
    )
    assert job.result["links"]["externalUrl"].endswith("?scope=external")
    assert job.api_calls.count() == 1
    assert job.api_calls.get().method == "JAVA"


@pytest.mark.django_db
def test_application_link_rejects_category_without_catalog_route(client) -> None:
    response = client.post(
        "/api/product-data/tools/application-links/generate",
        data=json.dumps(
            {
                "env": "UAT1",
                "product": "product-b",
                "category": "动态链接",
                "cooperationProjectId": "PROJECT-002",
                "payload": {"loanType": "首贷"},
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "未配置申请链接路由" in response.json()["message"]
    assert Job.objects.count() == 0
