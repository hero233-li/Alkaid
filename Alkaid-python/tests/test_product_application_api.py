import json
from unittest.mock import Mock, patch

import pytest
from django.test import Client
from pydantic import ValidationError

from apps.jobs.models import Job, JobStatus
from apps.jobs.services import JobRepository
from apps.product_data.product_applications.config import (
    CONFIG_PATH,
    load_product_application_config,
)
from apps.product_data.product_applications.schemas import ProductApplicationConfig
from apps.product_data.product_applications.tasks import execute_product_application

PRODUCT_TASK_DELAY = (
    "apps.product_data.product_applications.views.execute_product_application.delay"
)


def valid_submission() -> dict[str, object]:
    return {
        "name": "产品A-产品申请",
        "product": "product-a",
        "payload": {
            "environment": "env-1",
            "product": "product-a",
            "location": "广东省广州市",
            "branch": "广东省机构",
            "outlet": "广东省网点",
            "personName": "测试用户",
            "certificateNo": "330101199001011234",
            "phone": "13800138000",
            "cardNo": "6222000000000000",
            "customerType": "farmer",
            "whitelistEnabled": True,
            "redShieldEnabled": True,
        },
    }


def submission_for_product(
    product: str,
    switch_name: str,
    *,
    enabled: bool,
) -> dict[str, object]:
    submission = valid_submission()
    payload = submission["payload"]
    payload["product"] = product
    if product != "product-a":
        payload.update(
            {
                "location": "example-location",
                "branch": "example-branch",
                "outlet": "example-outlet",
            }
        )
    for configured_switch in ("whitelistEnabled", "redShieldEnabled", "creditEnabled"):
        payload.pop(configured_switch, None)
    payload[switch_name] = enabled
    if product == "product-a":
        payload["redShieldEnabled"] = True
    submission["product"] = product
    submission["name"] = f"{product}-产品申请"
    return submission


@pytest.mark.django_db
def test_product_application_config_matches_frontend_contract():
    response = Client().get("/api/product-data/applications/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["id"] == "product-application-example"
    assert payload["data"]["version"] == 4
    assert payload["data"]["environments"]
    assert payload["data"]["products"]
    assert payload["data"]["fields"]
    legal_person = next(
        field for field in payload["data"]["fields"] if field["name"] == "legalPerson"
    )
    assert legal_person["submit"] is False
    products = {item["value"]: item for item in payload["data"]["products"]}
    assert set(products) == {"product-a", "product-b", "product-c"}
    assert payload["data"]["fieldSets"]["redShield"] == ["redShieldEnabled"]
    assert products["product-a"]["fieldSets"] == [
        "selection",
        "customerBase",
        "enterprise",
        "whitelist",
        "redShield",
    ]
    switches = {
        field["name"]: field
        for field in payload["data"]["fields"]
        if field["name"] in {"whitelistEnabled", "redShieldEnabled", "creditEnabled"}
    }
    assert all("products" not in field for field in switches.values())


def test_product_application_config_is_reloaded_for_each_process_operation():
    config_path = Mock()
    config_path.read_text.return_value = CONFIG_PATH.read_text(encoding="utf-8")

    with patch("apps.product_data.product_applications.config.CONFIG_PATH", config_path):
        first = load_product_application_config()
        second = load_product_application_config()

    assert first.version == 4
    assert second.version == 4
    assert config_path.read_text.call_count == 2


def test_required_field_must_be_enabled_by_product_field_sets():
    content = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    content["products"][0]["requiredFields"].append("creditEnabled")

    with pytest.raises(ValidationError, match="必填字段未包含在字段组中"):
        ProductApplicationConfig.model_validate(content)


@pytest.mark.django_db(transaction=True)
def test_create_product_application_returns_numeric_job_and_enqueues_task():
    with patch(PRODUCT_TASK_DELAY) as delay:
        response = Client().post(
            "/api/product-data/applications",
            data=json.dumps(valid_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="product-request-1",
            HTTP_X_TRACE_ID="trace-1",
        )

    assert response.status_code == 202
    data = response.json()["data"]
    assert isinstance(data["id"], int)
    assert data["status"] == "pending"
    assert data["product"] == "product-a"
    assert data["payload"]["customerType"] == "farmer"
    assert data["payload"]["applicationMethod"] == "normal"
    assert data["executionConfigVersion"] == 5
    assert data["logs"][0]["message"] == "任务已创建，等待执行"
    delay.assert_called_once_with(data["id"])


@pytest.mark.django_db(transaction=True)
def test_product_application_is_idempotent():
    client = Client()
    with patch(PRODUCT_TASK_DELAY) as delay:
        first = client.post(
            "/api/product-data/applications",
            data=json.dumps(valid_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="product-request-2",
            HTTP_X_TRACE_ID="trace-2",
        )
        second = client.post(
            "/api/product-data/applications",
            data=json.dumps(valid_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="product-request-2",
            HTTP_X_TRACE_ID="trace-2",
        )

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert delay.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_product_application_task_updates_job_and_logs():
    with patch("apps.product_data.product_applications.views.execute_product_application.delay"):
        response = Client().post(
            "/api/product-data/applications",
            data=json.dumps(valid_submission()),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="product-request-3",
        )
    job_id = response.json()["data"]["id"]

    execute_product_application.apply(args=[job_id], throw=True)

    job = Job.objects.get(id=job_id)
    assert job.status == JobStatus.SUCCESS
    assert job.progress == 100
    assert job.celery_task_id
    assert job.result["validated"] is True
    assert job.result["customerType"] == "farmer"
    assert job.result["switch"] == "whitelistEnabled"
    assert job.result["switchEnabled"] is True
    assert job.result["flowTokenVersions"] == {
        "login": 1,
        "check": 1,
        "rotate": 2,
        "submit": 2,
    }
    assert job.result["fixedTokenCall"] == "success"
    assert job.result["executionConfigVersion"] == 5
    assert job.result["applicationMethod"] == "normal"
    assert job.result["operation"] == "mock_product.product_a.apply"
    assert job.result["productType"] == "whitelist_product"
    assert job.result["handler"] == "whitelist_application_v1"
    steps = list(job.logs.values_list("step", flat=True))
    for step in {
        "created",
        "validate",
        "auth.login",
        "product.check",
        "auth.rotate",
        "product.submit",
        "fixed.audit",
        "execute",
        "completed",
    }:
        assert step in steps
    assert job.api_calls.count() == 5
    submit_call = job.api_calls.get(step="product.submit")
    submit_body = submit_call.request_body["form"]["REQ_BODY"]
    submit_payload = submit_body["request"]
    assert submit_body["appId"] == "appohjkk1202307100001"
    assert submit_body["env"] == "UATC"
    assert submit_payload["cooperatorId"] == "JLHB"
    assert submit_payload["cooperatorName"] == "吉农e贷"
    assert submit_payload["custNme"] != "测试用户"
    assert submit_payload["idtyNo"] != "330101199001011234"
    assert submit_payload["distId"] == "220102"
    assert submit_payload["flowId"] == "JLHB100507"
    assert submit_payload["loanFlowStag"] == "1"
    assert submit_payload["selblProdId"] == "CJDK-JLHB"
    assert submit_payload["gbIndsTpCd"] == "A0143"
    assert submit_payload["spclCdtPolcyFlg"] == "02"
    assert submit_payload["loanPurpSubCatgCd"] == "26"
    assert submit_call.request_body["form"]["REQ_HEAD"] == {}
    audit_json = json.dumps(
        list(
            job.api_calls.values(
                "request_headers",
                "response_headers",
                "request_body",
                "response_body",
            )
        )
    )
    assert "flow-token-v1" not in audit_json
    assert "flow-token-v2" not in audit_json
    assert "mock-fixed-token" not in audit_json
    assert "330101199001011234" not in audit_json

    detail = Client().get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "success"


@pytest.mark.django_db(transaction=True)
def test_dynamic_application_uses_frozen_execution_snapshot():
    submission = valid_submission()
    submission["payload"].update(
        {
            "applicationMethod": "dynamic",
            "dynamicTerm": "12M",
            "dynamicAmount": "100000",
        }
    )
    with patch("apps.product_data.product_applications.views.execute_product_application.delay"):
        response = Client().post(
            "/api/product-data/applications",
            data=json.dumps(submission),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="dynamic-snapshot-1",
        )

    assert response.status_code == 202
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.execution_config_version == 5
    assert job.execution_config_snapshot["method_code"] == "dynamic"
    assert "dynamic_term" in job.execution_config_snapshot["fields"]

    with patch(
        "apps.product_data.product_applications.services.load_execution_catalog",
        side_effect=AssertionError("Worker must use the frozen Job snapshot"),
    ):
        execute_product_application.apply(args=[job.id], throw=True)

    job.refresh_from_db()
    assert job.status == JobStatus.SUCCESS
    assert job.result["applicationMethod"] == "dynamic"
    assert job.result["operation"] == "mock_product.product_a.dynamic_apply"


@pytest.mark.django_db
def test_dynamic_application_requires_its_configured_fields():
    submission = valid_submission()
    submission["payload"]["applicationMethod"] = "dynamic"

    response = Client().post(
        "/api/product-data/applications",
        data=json.dumps(submission),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "dynamicAmount" in response.json()["message"]
    assert "dynamicTerm" in response.json()["message"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("product", "switch_name", "enabled"),
    [
        ("product-a", "whitelistEnabled", True),
        ("product-b", "redShieldEnabled", False),
        ("product-c", "creditEnabled", True),
    ],
)
def test_each_mock_product_uses_only_its_associated_switch(product, switch_name, enabled):
    submission = submission_for_product(product, switch_name, enabled=enabled)
    with patch("apps.product_data.product_applications.views.execute_product_application.delay"):
        response = Client().post(
            "/api/product-data/applications",
            data=json.dumps(submission),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY=f"switch-{product}",
        )
    assert response.status_code == 202

    job_id = response.json()["data"]["id"]
    execute_product_application.apply(args=[job_id], throw=True)

    job = Job.objects.get(id=job_id)
    assert job.result["switch"] == switch_name
    assert job.result["switchEnabled"] is enabled


@pytest.mark.django_db
def test_product_rejects_a_field_outside_its_field_sets():
    submission = valid_submission()
    submission["payload"]["creditEnabled"] = True

    response = Client().post(
        "/api/product-data/applications",
        data=json.dumps(submission),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "creditEnabled" in response.json()["message"]


@pytest.mark.django_db
def test_invalid_product_payload_is_rejected_without_job():
    submission = valid_submission()
    submission["payload"] = {"environment": "unknown"}

    response = Client().post(
        "/api/product-data/applications",
        data=json.dumps(submission),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert Job.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("customer_type", "company_name"),
    [
        ("legal_person", "示例企业"),
        ("shareholder", "示例企业"),
    ],
)
def test_company_customer_types_require_and_accept_company_name(customer_type, company_name):
    submission = valid_submission()
    submission["payload"]["customerType"] = customer_type
    submission["payload"]["companyName"] = company_name

    with patch("apps.product_data.product_applications.views.execute_product_application.delay"):
        response = Client().post(
            "/api/product-data/applications",
            data=json.dumps(submission),
            content_type="application/json",
        )

    assert response.status_code == 202
    assert response.json()["data"]["payload"]["customerType"] == customer_type


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload_update", "message"),
    [
        ({"customerType": "unknown"}, "customerType 必须是"),
        ({"customerType": "legal_person"}, "必须填写企业名称"),
        ({"customerType": "shareholder"}, "必须填写企业名称"),
        ({"customerType": "farmer", "companyName": "示例企业"}, "必须是法人或股东"),
        ({"customerType": "farmer", "legalPerson": True}, "legalPerson 布尔字段已停用"),
    ],
)
def test_customer_type_and_company_name_must_be_consistent(payload_update, message):
    submission = valid_submission()
    submission["payload"].update(payload_update)

    response = Client().post(
        "/api/product-data/applications",
        data=json.dumps(submission),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert message in response.json()["message"]


@pytest.mark.django_db(transaction=True)
def test_failed_job_can_be_retried_and_pending_job_can_be_cancelled():
    failed = JobRepository.create(
        kind="product_application",
        name="失败任务",
        product="product-a",
        payload=valid_submission()["payload"],
        trace_id="retry-trace",
        idempotency_key="retry-job-1",
        timeout_seconds=30,
    ).job
    JobRepository.mark_failed(failed.id, "模拟失败")

    with patch("apps.jobs.views._enqueue") as enqueue:
        retry_response = Client().post(f"/api/jobs/{failed.id}/retry")

    assert retry_response.status_code == 200
    assert retry_response.json()["data"]["status"] == "retrying"
    assert retry_response.json()["data"]["attemptCount"] == 2
    enqueue.assert_called_once()

    pending = JobRepository.create(
        kind="product_application",
        name="等待任务",
        product="product-a",
        payload=valid_submission()["payload"],
        trace_id="cancel-trace",
        idempotency_key="cancel-job-1",
        timeout_seconds=30,
    ).job
    cancel_response = Client().post(f"/api/jobs/{pending.id}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "cancelled"
