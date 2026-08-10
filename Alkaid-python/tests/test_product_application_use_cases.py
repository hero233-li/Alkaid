"""Product application function Use Case tests."""

import json

import pytest
from django.test import override_settings

import apps.workflow.product_applications.tasks as task_module
from apps.utils.application_links import compile_application_link_plan
from apps.utils.http import config
from apps.utils.product_Conf.catalog import load_product_catalog
from apps.workflow.Jobs.integration_observer import JobIntegrationObserver
from apps.workflow.Jobs.models import JobStatus
from apps.workflow.Jobs.services import create_job
from apps.workflow.product_applications.api import (
    ProductApplicationSubmission,
    ProductConfigurationError,
)
from apps.workflow.product_applications.cjdk.client import CjdkClient
from apps.workflow.product_applications.cjdk.runtime import ProductApplicationRuntime
from apps.workflow.product_applications.identity.dcpp import DcppClient
from apps.workflow.product_applications.identity.photo import PhotoClient
from apps.workflow.product_applications.workflow import (
    execute_product_application,
    freeze_product_execution_snapshot,
)


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
    return freeze_product_execution_snapshot(
        submission,
        load_product_catalog(),
        plan_compiler=compile_application_link_plan,
    )[1]


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
    runtime = ProductApplicationRuntime(
        settings=config.get_cjdk_jyrc_settings(),
        observer=JobIntegrationObserver(job),
        trace_id=job.trace_id,
        environment=snapshot.environment,
    )
    assert runtime.photo_client is None
    assert runtime.dcpp_client is None
    progress_stages: list[str] = []
    result = execute_product_application(
        runtime=runtime,
        submission=submission,
        snapshot=snapshot,
        application_link_kind="internal",
        progress=lambda **event: progress_stages.append(event["stage"]),
    )

    assert result["applicationLink"] == {
        "generated": True,
        "category": "太阳码",
        "selected": "internal",
    }
    assert result["agreementReadCompleted"] is True
    assert result["agreementTemplates"][0]["fcosTemplateNo"] == "2209201448031"
    assert result["agreementPreview"]["Documents"][0]["docId"] == "MOCK-DOC-ID-001"
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
    assert result["identityVerificationCompleted"] is True
    assert result["identityVerification"]["plainCustomerName"] == "测试用户"
    assert result["identityVerification"]["plainIdentityNo"] == "330101199001011234"
    assert result["identityVerification"]["plainMobile"] == "13800138000"
    assert result["identityVerification"]["cardNo"] == "6222000000000000"
    assert result["identityVerification"]["license"] == "MOCK-FACE-LICENSE"
    assert result["identityVerification"]["smsCode"] == "123456"
    assert result["identityVerification"]["verification"]["rawResponse"]["verified"] is True

    steps = list(job.api_calls.order_by("id").values_list("step", flat=True))
    assert steps[0] == "application_link.generate_link"
    assert steps[-1] == "identity.card_verify"
    assert steps.count("agreement.query_templates") == 2
    assert "application_link.acquire_session" in steps
    agreement_calls = job.api_calls.filter(step="agreement.query_templates").order_by("id")
    scenes = [
        json.loads(call.request_body["form"]["REQ_MESSAGE"])["REQ_BODY"]["request"]["scene"]
        for call in agreement_calls
    ]
    assert scenes == ["SC00015", "SC00016"]
    assert progress_stages == [
        "validate",
        "application_link",
        "session",
        "agreement_query",
        "agreement_preview",
        "agreement_read",
        "application_submit",
        "identity_public_key",
        "identity_mobile",
        "identity_agreement_query",
        "identity_agreement_preview",
        "identity_agreement_read",
        "identity_photo_delete",
        "identity_face_check",
        "identity_sms_check",
        "identity_verify",
    ]


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
        def open(self):
            raise AssertionError("validation failure must not open an external runtime")

    with pytest.raises(ProductConfigurationError, match="personName"):
        execute_product_application(
            runtime=UnexpectedRuntime(),
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
    assert isinstance(captured["runtime"], ProductApplicationRuntime)
    assert captured["application_link_kind"] == "internal"
    assert callable(captured["progress"])
    assert job.status == JobStatus.SUCCESS
    assert job.result == expected_result


@pytest.mark.django_db
@override_settings(EXTERNAL_SYSTEM_MODE="mock", APPLICATION_LINK_URL_MODE="internal")
def test_mock_task_completes_identity_verification() -> None:
    job = _job(key="mock-full-identity-task")

    task_module.execute_product_application.apply(args=(job.id,), throw=True)

    job.refresh_from_db()
    assert job.status == JobStatus.SUCCESS
    assert job.result["identityVerificationCompleted"] is True


@pytest.mark.django_db
@override_settings(EXTERNAL_SYSTEM_MODE="mock")
def test_cjdk_photo_and_dcpp_clients_have_independent_lifecycles() -> None:
    job = _job(key="client-isolation")
    settings = config.get_cjdk_jyrc_settings()
    cjdk = CjdkClient(
        settings=settings,
        observer=JobIntegrationObserver(job),
        trace_id=job.trace_id,
        environment="UAT1",
    )
    photo = PhotoClient(
        config.PhotoEnvironmentSettings(baseUrl="https://photo.invalid", verifySsl=False)
    )
    dcpp = DcppClient({})

    cjdk.open()
    photo.open()
    try:
        assert cjdk._http_client is not None
        clients = (cjdk._http_client._client, photo._client, dcpp._client)
        assert all(client is not None for client in clients)
        assert len({id(client) for client in clients}) == 3
        assert len({id(client.cookies.jar) for client in clients if client is not None}) == 3
    finally:
        cjdk.close()
        photo.close()
        dcpp.close()

    assert cjdk._http_client is None
    assert photo._client is None
    assert dcpp._client.is_closed


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
    from apps.utils.product_Conf.catalog import CatalogField

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
