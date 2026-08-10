import json
from copy import deepcopy

import pytest

import apps.utils.application_links.plans as plan_module
import apps.utils.product_Conf.catalog as catalog_module
from apps.utils.application_links import compile_application_link_plan
from apps.utils.java.application_link import build_application_link_request
from apps.utils.product_Conf.catalog import FrozenApplicationLinkRoute, load_product_catalog
from apps.workflow.Jobs.services import create_job
from apps.workflow.product_applications.api import (
    ProductApplicationSubmission,
    ProductConfigurationError,
)
from apps.workflow.product_applications.workflow import (
    execute_product_application,
    freeze_product_execution_snapshot,
    resolve_product_snapshot,
)


class SnapshotSecretResolver:
    def resolve(self, reference: str) -> str:
        return f"secret-for-{reference}"


def _submission() -> ProductApplicationSubmission:
    return ProductApplicationSubmission(
        name="产品B申请",
        product="product-b",
        payload={
            "environment": "UAT1",
            "product": "product-b",
            "location": "example-location",
            "branch": "example-branch",
            "outlet": "example-outlet",
            "cooperationProjectId": "PROJECT-002",
            "personName": "测试用户",
            "certificateNo": "330101199001011234",
            "cardNo": "6222000000000000",
            "phone": "13800138000",
            "customerType": "farmer",
            "applicationMethod": "normal",
            "redShieldEnabled": True,
            "idType": "01",
        },
    )


@pytest.mark.django_db
def test_worker_uses_frozen_v1_plan_without_loading_current_catalog(monkeypatch) -> None:
    submission = _submission()
    original_submission = submission.model_copy(deep=True)
    prepared = freeze_product_execution_snapshot(
        submission,
        load_product_catalog(),
        plan_compiler=compile_application_link_plan,
    )
    prepared_submission, snapshot = prepared
    assert submission == original_submission
    assert prepared_submission is not submission
    serialized_snapshot = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)
    assert "PRIVATE-KEY" not in serialized_snapshot
    assert "PUBLIC-KEY" not in serialized_snapshot
    assert "APP-ID" not in serialized_snapshot
    assert [step.module for step in snapshot.workflow] == [
        "application.apply",
        "identity.verify",
    ]
    assert '"workflow"' in serialized_snapshot
    assert snapshot.application_link_route.secret_bindings == {}
    original_order_no = snapshot.application_link_route.compiled_request_template["REQ_BODY"][
        "request"
    ]["order_no"]
    changed_v2 = deepcopy(snapshot.application_link_route.compiled_request_template)
    changed_v2["REQ_BODY"]["request"]["order_no"] = "V2-MUST-NOT-BE-USED"
    job = create_job(
        kind="product_application",
        name=submission.name,
        product=submission.product,
        payload=submission.payload,
        trace_id="snapshot-v1",
        idempotency_key="snapshot-v1",
        timeout_seconds=60,
        execution_config_version=snapshot.catalog_version,
        execution_config_snapshot=snapshot.model_dump(mode="json"),
    ).job
    captured: dict[str, object] = {}

    def forbidden_catalog_load(*args, **kwargs):
        raise AssertionError("Worker 不允许读取当前 Catalog")

    monkeypatch.setattr(catalog_module, "load_product_catalog", forbidden_catalog_load)
    monkeypatch.setattr(plan_module, "load_integration_profile", forbidden_catalog_load)

    class FrozenPlanPort:
        settings = None
        observer = None
        trace_id = "test"

        def __init__(self):
            self.client = self

        def open(self):
            return None

        def close(self):
            return None

        def execute_application(self, *, snapshot, **kwargs):
            request = build_application_link_request(
                plan=FrozenApplicationLinkRoute.model_validate(snapshot.application_link_route),
                normalized_payload=dict(snapshot.normalized_payload),
                secret_resolver=SnapshotSecretResolver(),
            )
            captured["request"] = request
            raise StopAfterApplicationLink()

    class StopAfterApplicationLink(RuntimeError):
        pass

    monkeypatch.setattr(
        "apps.workflow.product_applications.modules.application.execute_application",
        lambda client, **kwargs: client.execute_application(**kwargs),
    )

    with pytest.raises(StopAfterApplicationLink):
        execute_product_application(
            runtime=FrozenPlanPort(),
            submission=ProductApplicationSubmission(
                name=job.name,
                product=snapshot.product_code,
                payload=dict(snapshot.normalized_payload),
            ),
            snapshot=resolve_product_snapshot(job, job.product),
            application_link_kind="internal",
        )

    assert changed_v2["REQ_BODY"]["request"]["order_no"] == "V2-MUST-NOT-BE-USED"
    assert captured["request"]["payload"]["REQ_BODY"]["request"]["order_no"] == original_order_no


@pytest.mark.django_db
def test_legacy_job_without_frozen_route_is_rejected() -> None:
    job = create_job(
        kind="product_application",
        name="旧任务",
        product="product-b",
        payload={},
        trace_id="legacy-snapshot",
        idempotency_key="legacy-snapshot",
        timeout_seconds=60,
        execution_config_version=1,
        execution_config_snapshot={"product_code": "product-b"},
    ).job
    with pytest.raises(ProductConfigurationError, match="请重新创建任务"):
        resolve_product_snapshot(job, "product-b")
