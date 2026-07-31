import pytest

import apps.product_data.product_applications.flow as flow_module
import apps.product_data.product_applications.tasks as task_module
from apps.integrations.mock_product.models import OperationResponse, RequestHead
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
def test_product_application_flow_executes_steps_in_python_order(monkeypatch) -> None:
    job = _job(key="product-flow-order")
    calls: list[str] = []

    class StubAdapter:
        def __init__(self, job_arg) -> None:
            assert job_arg == job
            self.version = 0

        def __enter__(self):
            calls.append("enter")
            return self

        def __exit__(self, *args):
            calls.append("exit")
            return None

        @property
        def flow_token_version(self) -> int:
            return self.version

        def request_head(self) -> RequestHead:
            calls.append("request_head")
            return RequestHead(
                traceno=job.trace_id,
                starttime="20260731084900",
                product=job.product,
            )

        def login(self, head: RequestHead) -> None:
            assert head.product == "product-b"
            calls.append("login")
            self.version = 1

        def check_product(self, head, request) -> OperationResponse:
            assert request.product == "product-b"
            assert request.switch_name == "redShieldEnabled"
            calls.append("check_product")
            return OperationResponse(code="0000", message="success")

        def rotate_token(self, head: RequestHead) -> None:
            calls.append("rotate_token")
            self.version = 2

        def submit_application(self, head, request) -> OperationResponse:
            assert request.customer_name == "测试用户"
            calls.append("submit_application")
            return OperationResponse(
                code="0000",
                message="success",
                data={"applicationNo": "APP-FLOW-001"},
            )

        def audit(self, head: RequestHead) -> None:
            calls.append("audit")

    monkeypatch.setattr(flow_module, "MockProductApplicationAdapter", StubAdapter)

    result = ProductApplicationFlow().execute(job=job)

    assert calls == [
        "enter",
        "request_head",
        "login",
        "check_product",
        "rotate_token",
        "submit_application",
        "audit",
        "exit",
    ]
    assert result["applicationNo"] == "APP-FLOW-001"
    assert result["flowTokenVersions"] == {
        "login": 1,
        "check": 1,
        "rotate": 2,
        "submit": 2,
    }
    assert result["fixedTokenCall"] == "success"


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
        raise AssertionError("validation failure must not open the external adapter")

    monkeypatch.setattr(flow_module, "MockProductApplicationAdapter", unexpected_adapter)

    with pytest.raises(ProductConfigurationError, match="personName"):
        ProductApplicationFlow().execute(job=job)


@pytest.mark.django_db
def test_product_application_task_delegates_to_flow(monkeypatch) -> None:
    job = _job(key="product-task-flow")
    captured: dict[str, object] = {}
    expected_result = {
        "applicationNo": "APP-STUB-001",
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
