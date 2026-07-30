import pytest

import apps.product_data.application_links.flow as flow_module
import apps.product_data.application_links.services as services_module
import apps.product_data.application_links.tasks as task_module
from apps.jobs.models import JobStatus
from apps.jobs.services import create_job
from apps.product_data.application_links.flow import ApplicationLinkFlow
from apps.product_data.application_links.schemas import (
    ApplicationLinkExecutionSnapshot,
    ApplicationLinkResult,
)
from apps.product_data.application_links.services import (
    ApplicationLinkConfigurationError,
)


def _snapshot(*, required_fields: tuple[str, ...] = ("loanType",)) -> dict[str, object]:
    return ApplicationLinkExecutionSnapshot(
        config_version=1,
        product="product-b",
        environment="env-1",
        category="太阳码",
        required_fields=required_fields,
    ).model_dump(mode="json")


def _job(
    *,
    key: str,
    payload: dict[str, object] | None = None,
    snapshot: dict[str, object] | None = None,
):
    return create_job(
        kind="application_link_generation",
        name="申请链接生成-product-b",
        product="product-b",
        payload=payload
        or {
            "env": "env-1",
            "product": "product-b",
            "category": "太阳码",
            "cooperationProjectId": "PROJECT-001",
            "payload": {"loanType": "经营贷"},
        },
        trace_id=f"trace-{key}",
        idempotency_key=key,
        timeout_seconds=60,
        execution_config_snapshot=snapshot,
    ).job


def _result() -> ApplicationLinkResult:
    return ApplicationLinkResult(
        internalUrl="https://internal.example/link",
        externalUrl="https://external.example/link",
        generatedAt="2026-07-30T00:00:00+00:00",
    )


@pytest.mark.django_db
def test_flow_uses_frozen_execution_snapshot(monkeypatch) -> None:
    job = _job(key="flow-frozen-snapshot", snapshot=_snapshot())
    captured: dict[str, object] = {}

    def generate(job_arg, submission, *, snapshot):
        captured.update(job=job_arg, submission=submission, snapshot=snapshot)
        return _result()

    monkeypatch.setattr(flow_module, "generate_application_links", generate)

    result = ApplicationLinkFlow().execute(job=job)

    assert result == _result()
    assert captured["job"] == job
    assert captured["submission"].environment == "env-1"
    assert captured["snapshot"].model_dump(mode="json") == _snapshot()


@pytest.mark.django_db
def test_flow_normalizes_and_resolves_snapshot_for_legacy_job(monkeypatch) -> None:
    job = _job(
        key="flow-legacy-job",
        payload={
            "env": "环境1",
            "product": "产品B",
            "category": "太阳码",
            "cooperationProjectId": "合作项目一",
            "payload": {"loanType": "经营贷"},
        },
    )
    captured: dict[str, object] = {}

    def generate(job_arg, submission, *, snapshot):
        captured.update(job=job_arg, submission=submission, snapshot=snapshot)
        return _result()

    monkeypatch.setattr(flow_module, "generate_application_links", generate)

    ApplicationLinkFlow().execute(job=job)

    submission = captured["submission"]
    snapshot = captured["snapshot"]
    assert submission.product == "product-b"
    assert submission.environment == "env-1"
    assert submission.cooperationProjectId == "PROJECT-001"
    assert snapshot.product == "product-b"
    assert snapshot.environment == "env-1"


@pytest.mark.django_db
def test_flow_rejects_invalid_submission_before_external_call(monkeypatch) -> None:
    job = _job(
        key="flow-invalid-submission",
        payload={
            "env": "env-1",
            "product": "product-b",
            "category": "太阳码",
            "cooperationProjectId": "PROJECT-001",
            "payload": {},
        },
        snapshot=_snapshot(),
    )

    def unexpected_generate(*args, **kwargs):
        raise AssertionError("validation failure must not call the external adapter")

    monkeypatch.setattr(flow_module, "generate_application_links", unexpected_generate)

    with pytest.raises(ApplicationLinkConfigurationError, match="loanType"):
        ApplicationLinkFlow().execute(job=job)


@pytest.mark.django_db
def test_flow_propagates_application_link_adapter_failure(monkeypatch) -> None:
    job = _job(key="flow-adapter-failure", snapshot=_snapshot())

    class FailingAdapter:
        def __init__(self, job_arg) -> None:
            assert job_arg == job

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def generate_link(self, request):
            raise RuntimeError("external application-link service unavailable")

    monkeypatch.setattr(services_module, "ApplicationLinkAdapter", FailingAdapter)

    with pytest.raises(RuntimeError, match="external application-link service unavailable"):
        ApplicationLinkFlow().execute(job=job)


@pytest.mark.django_db
def test_task_delegates_to_flow_and_keeps_result_contract(monkeypatch) -> None:
    job = _job(key="task-delegates-to-flow", snapshot=_snapshot())
    captured: dict[str, object] = {}

    class StubFlow:
        def execute(self, *, job, progress):
            captured.update(job=job, progress=progress)
            return _result()

    monkeypatch.setattr(task_module, "ApplicationLinkFlow", StubFlow)

    task_module.execute_application_link.apply(args=(job.id,), throw=True)

    job.refresh_from_db()
    assert captured["job"].id == job.id
    assert callable(captured["progress"])
    assert job.status == JobStatus.SUCCESS
    assert job.result == {"links": _result().model_dump(mode="json")}
