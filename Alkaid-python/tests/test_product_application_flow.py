import pytest
from django.test import override_settings

import apps.product_data.product_applications.flow as flow_module
import apps.product_data.product_applications.tasks as task_module
from apps.jobs.models import JobStatus
from apps.jobs.services import create_job
from apps.product_data.catalog import load_product_catalog
from apps.product_data.product_applications.flow import ProductApplicationFlow
from apps.product_data.product_applications.services import ProductConfigurationError


def _payload() -> dict[str, object]:
    return {
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
        "idType": "01",
        "projectId": "PROJECT-001",
    }


def _snapshot():
    return load_product_catalog().snapshot("product-b")


def _job(*, key: str, payload=None, snapshot=None):
    resolved_snapshot = snapshot or _snapshot()
    return create_job(
        kind="product_application",
        name="产品B申请",
        product="product-b",
        payload=payload or _payload(),
        trace_id=f"trace-{key}",
        idempotency_key=key,
        timeout_seconds=60,
        execution_config_version=resolved_snapshot.catalog_version,
        execution_config_snapshot=resolved_snapshot.model_dump(mode="json"),
    ).job


@pytest.mark.django_db
@override_settings(EXTERNAL_SYSTEM_MODE="mock", APPLICATION_LINK_URL_MODE="internal")
def test_product_application_flow_opens_link_then_reads_agreement() -> None:
    job = _job(key="agreement-flow")

    result = ProductApplicationFlow().execute(job=job)

    assert result["applicationLink"] == {
        "generated": True,
        "category": "太阳码",
        "selected": "internal",
    }
    assert result["agreementReadCompleted"] is True
    assert result["agreementTemplates"][0]["fcosTemplateNo"] == "2209201448031"
    assert result["agreementPreview"]["documents"][0]["docId"] == "MOCK-DOC-ID-001"
    assert result["agreementDocuments"][0]["fileName"] == "mock-agreement.pdf"
    assert result["agreementDocuments"][0]["contentBytes"] > 0
    assert result["externalSession"]["established"] is True
    assert result["externalSession"]["cookieNames"] == [
        "JSESSIONID",
        "link_entry",
        "token_id",
    ]
    assert result["externalSession"]["forwardedHeaderNames"] == [
        "X-FCOS-SESSIONID",
        "X-Sd",
        "X-Token",
    ]
    assert result["externalSession"]["finalUrlPresent"] is True

    assert list(job.api_calls.order_by("id").values_list("step", flat=True)) == [
        "application_link.generate_link",
        "application_link.acquire_session",
        "agreement.query_templates",
        "agreement.query_preview",
        "agreement.read_document",
    ]


@pytest.mark.django_db
def test_product_application_flow_validates_before_opening_adapter(monkeypatch) -> None:
    snapshot = _snapshot().model_copy(update={"required_fields": ("personName",)})
    payload = _payload()
    payload.pop("personName")
    job = _job(
        key="product-flow-invalid",
        payload=payload,
        snapshot=snapshot,
    )

    def unexpected_adapter(*args, **kwargs):
        raise AssertionError("validation failure must not open an external adapter")

    monkeypatch.setattr(
        flow_module,
        "CjdkJyrcApplicationLinkAdapter",
        unexpected_adapter,
    )
    monkeypatch.setattr(flow_module, "CjdkJyrcAgreementAdapter", unexpected_adapter)

    with pytest.raises(ProductConfigurationError, match="personName"):
        ProductApplicationFlow().execute(job=job)


@pytest.mark.django_db
def test_product_application_task_delegates_to_flow(monkeypatch) -> None:
    job = _job(key="product-task-flow")
    captured: dict[str, object] = {}
    expected_result = {
        "agreementReadCompleted": True,
        "validated": True,
    }

    class StubFlow:
        def execute(self, *, job, progress):
            captured.update(job=job, progress=progress)
            return expected_result

    monkeypatch.setattr(task_module, "ProductApplicationFlow", StubFlow)

    task_module.execute_product_application.apply(args=(job.id,), throw=True)

    job.refresh_from_db()
    assert captured["job"].id == job.id
    assert callable(captured["progress"])
    assert job.status == JobStatus.SUCCESS
    assert job.result == expected_result


@override_settings(
    EXTERNAL_SYSTEM_MODE="real",
    CJDK_JYRC_BASE_URLS={
        "uat1": "http://uat1.example:8090/",
        "uat2": "http://uat2.example:8091",
    },
    APPLICATION_LINK_BASE_URLS={
        "uat1": "http://link-uat1.example:8080/",
        "uat2": "http://link-uat2.example:8081",
    },
)
def test_environment_selects_its_own_base_urls() -> None:
    from apps.integrations.cjdk_jyrc.config import (
        resolve_application_link_base_url,
        resolve_base_url,
    )

    assert resolve_base_url("uat1") == "http://uat1.example:8090"
    assert resolve_base_url("UAT2") == "http://uat2.example:8091"
    assert resolve_application_link_base_url("uat1") == "http://link-uat1.example:8080"
    assert resolve_application_link_base_url("UAT2") == "http://link-uat2.example:8081"
