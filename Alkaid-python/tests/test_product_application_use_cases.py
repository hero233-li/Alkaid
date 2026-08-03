"""Product application function Use Case tests."""

import pytest
from django.test import override_settings

import apps.product_data.product_applications.tasks as task_module
from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.runtime import CjdkJyrcRuntime
from apps.jobs.integration_observer import JobIntegrationObserver
from apps.jobs.models import JobStatus
from apps.jobs.services import create_job
from apps.product_data.catalog import load_product_catalog
from apps.product_data.product_applications.preparation import freeze_product_execution_snapshot
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.use_cases import execute_product_application
from apps.product_data.product_applications.validation import ProductConfigurationError


def _payload() -> dict[str, object]:
    return {
        "environment": "UAT1",
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
        "projectId": "PROJECT-002",
    }


def _snapshot(payload=None):
    submission = ProductApplicationSubmission(
        name="产品B申请",
        product="product-b",
        payload=payload or _payload(),
    )
    return freeze_product_execution_snapshot(submission, load_product_catalog()).snapshot


def _job(*, key: str, payload=None, snapshot=None):
    resolved_payload = payload or _payload()
    resolved_snapshot = snapshot or _snapshot(resolved_payload)
    return create_job(
        kind="product_application",
        name="产品B申请",
        product="product-b",
        payload=resolved_payload,
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
    snapshot = _snapshot()
    submission = ProductApplicationSubmission(
        name=job.name, product=job.product, payload=dict(snapshot.normalized_payload)
    )
    runtime = CjdkJyrcRuntime(
        settings=config.get_cjdk_jyrc_settings(),
        observer=JobIntegrationObserver(job),
        trace_id=job.trace_id,
        environment=snapshot.environment,
    )
    assert runtime.external_session._client is runtime.agreements._client
    assert runtime._client._observer is runtime.application_links._java_gateway._observer
    result = execute_product_application(
        runtime=runtime,
        application_links=runtime.application_links,
        external_session=runtime.external_session,
        agreements=runtime.agreements,
        submission=submission,
        snapshot=snapshot,
        application_link_kind="internal",
    )

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

    steps = list(job.api_calls.order_by("id").values_list("step", flat=True))
    assert steps[0] == "application_link.generate_link"
    assert steps[-3:] == [
        "agreement.query_templates",
        "agreement.query_preview",
        "agreement.read_document",
    ]
    assert "application_link.acquire_session" in steps


@pytest.mark.django_db
def test_product_application_flow_validates_before_opening_adapter() -> None:
    payload = _payload()
    payload.pop("personName")
    frozen_payload = _payload()
    frozen_payload.pop("personName")
    snapshot = _snapshot().model_copy(
        update={
            "required_fields": ("personName",),
            "normalized_payload": frozen_payload,
        }
    )
    job = _job(
        key="product-flow-invalid",
        payload=payload,
        snapshot=snapshot,
    )

    class UnexpectedRuntime:
        def __enter__(self):
            raise AssertionError("validation failure must not open an external runtime")

    with pytest.raises(ProductConfigurationError, match="personName"):
        execute_product_application(
            runtime=UnexpectedRuntime(),
            application_links=object(),
            external_session=object(),
            agreements=object(),
            submission=ProductApplicationSubmission(
                name=job.name, product=job.product, payload=frozen_payload
            ),
            snapshot=snapshot,
            application_link_kind="internal",
        )


@pytest.mark.django_db
def test_product_application_task_delegates_to_use_case(monkeypatch) -> None:
    job = _job(key="product-task-flow")
    captured: dict[str, object] = {}
    expected_result = {
        "agreementReadCompleted": True,
        "validated": True,
    }

    def stub_execute(**kwargs):
        captured.update(kwargs)
        return expected_result

    monkeypatch.setattr(task_module, "execute_product_application_use_case", stub_execute)

    task_module.execute_product_application.apply(args=(job.id,), throw=True)

    job.refresh_from_db()
    assert isinstance(captured["runtime"], CjdkJyrcRuntime)
    runtime = captured["runtime"]
    assert captured["application_links"] is runtime.application_links
    assert captured["external_session"] is runtime.external_session
    assert captured["agreements"] is runtime.agreements
    assert captured["application_link_kind"] == "internal"
    assert callable(captured["progress"])
    assert job.status == JobStatus.SUCCESS
    assert job.result == expected_result


@override_settings(
    EXTERNAL_SYSTEM_MODE="real",
    CJDK_JYRC_BASE_URLS={"UAT1": "http://django-setting.example:8090"},
    APPLICATION_LINK_JAVA_SDK_DIR="D:/django-sdk",
)
def test_local_environment_config_has_highest_priority(tmp_path, monkeypatch) -> None:
    local_path = tmp_path / "environments.local.json"
    local_path.write_text(
        """{
          "mode": "real",
          "applicationLinkUrlMode": "external",
          "javaGateway": {
            "sdkDir": "D:/local-sdk",
            "javaExecutable": "D:/jdk/bin/java.exe",
            "jar": "application-link.jar",
            "mainClass": "com.example.LocalMain",
            "outputEncoding": "gbk",
            "timeoutSeconds": 33
          },
          "environments": {
            "UAT1": {"agreementBaseUrl": "http://local.example:8091/"}
          }
        }""",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "LOCAL_ENVIRONMENT_CONFIG_PATH", local_path)
    config.clear_environment_config_cache()

    configured = config.get_cjdk_jyrc_settings()

    assert configured.java_gateway.sdk_dir.as_posix() == "D:/local-sdk"
    assert configured.java_gateway.main_class == "com.example.LocalMain"
    assert configured.java_gateway.timeout_seconds == 33
    assert configured.application_link_url_mode == "external"
    assert config.resolve_base_url("uat1") == "http://local.example:8091"


def test_requiredness_is_not_stored_on_global_ui_field() -> None:
    from apps.product_data.catalog import CatalogField

    required_for_product = CatalogField(
        name="sharedField",
        group="base",
        requiredFor=("*",),
    )
    optional_for_product = CatalogField(
        name="sharedField",
        group="base",
    )

    assert required_for_product.required_for("normal") is True
    assert optional_for_product.required_for("normal") is False
    assert required_for_product.as_ui_field() == optional_for_product.as_ui_field()
    assert required_for_product.as_ui_field().required is False
