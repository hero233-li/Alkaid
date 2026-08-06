from copy import deepcopy

from apps.jobs.models import Job
from apps.product_data.application_link_plan import compile_application_link_plan
from apps.product_data.catalog import ProductCatalog, ProductExecutionSnapshot
from apps.product_data.product_applications.results import PreparedProductApplication
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.validation import (
    ProductConfigurationError,
    normalize_environment,
    validate_and_normalize_payload,
    validate_customer_rules,
    validate_location_hierarchy,
    validate_submission,
)


def freeze_product_execution_snapshot(
    submission: ProductApplicationSubmission,
    catalog: ProductCatalog,
) -> PreparedProductApplication:
    payload = deepcopy(submission.payload)
    product = catalog.product(submission.product)
    environment = normalize_environment(payload.get("environment"), catalog)
    method = product.method(str(payload.get("applicationMethod") or "") or None)

    payload["environment"] = environment
    payload["product"] = submission.product
    payload["applicationMethod"] = method.code

    configured_project_id = product.cooperationProjectId
    provided_project_ids = (
        payload.pop("projectId", None),
        payload.pop("cooperationProjectId", None),
    )
    if configured_project_id is None:
        if any(value not in {None, ""} for value in provided_project_ids):
            raise ProductConfigurationError("当前产品未绑定合作项目")
    else:
        if any(
            value not in {None, ""} and value != configured_project_id
            for value in provided_project_ids
        ):
            raise ProductConfigurationError("合作项目与产品配置不一致")
        payload["cooperationProjectId"] = configured_project_id

    payload = validate_and_normalize_payload(
        product=product,
        method_code=method.code,
        raw_payload=payload,
    )
    validate_location_hierarchy(product.locations, payload)
    validate_customer_rules(payload)

    plan = compile_application_link_plan(
        catalog=catalog,
        product_code=product.code,
        environment=environment,
        method_code=method.code,
    )
    snapshot = catalog.snapshot(
        product.code,
        method.code,
        environment=environment,
        normalized_payload=deepcopy(payload),
        application_link_route=plan.freeze(),
    )
    normalized_submission = ProductApplicationSubmission(
        name=submission.name,
        product=submission.product,
        payload=payload,
    )
    validate_submission(normalized_submission, execution_snapshot=snapshot, catalog=catalog)
    frozen_snapshot = snapshot.model_copy(
        update={"normalized_payload": deepcopy(normalized_submission.payload)}
    )
    return PreparedProductApplication(submission=normalized_submission, snapshot=frozen_snapshot)


def resolve_product_snapshot(job: Job, product_code: str) -> ProductExecutionSnapshot:
    if not job.execution_config_snapshot:
        raise ProductConfigurationError("历史 Job 缺少冻结的申请链接执行配置，请重新创建任务")
    try:
        snapshot = ProductExecutionSnapshot.model_validate(job.execution_config_snapshot)
    except ValueError as exc:
        raise ProductConfigurationError(
            "历史 Job 缺少冻结的申请链接执行配置，请重新创建任务"
        ) from exc
    if snapshot.product_code != product_code:
        raise ProductConfigurationError("Job 产品与冻结执行配置不一致")
    return snapshot
