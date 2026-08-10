from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any, Literal

from apps.utils.product_Conf.catalog import (
    FrozenApplicationLinkRoute,
    ProductCatalog,
    ProductExecutionSnapshot,
    load_product_catalog,
)
from apps.workflow.Jobs.models import Job
from apps.workflow.Jobs.services import (
    CreatedJob,
    add_business_log,
    create_job,
    resolve_job_identifiers,
)
from apps.workflow.product_applications.workflow_engine import (
    ApplicationModuleOutcome,
    IdentityModuleOutcome,
    WorkflowExecutionContext,
    execute_product_workflow,
    validate_product_workflow,
)

from .schemas import ProductApplicationSubmission
from .validation import (
    ProductConfigurationError,
    normalize_environment,
    validate_and_normalize_payload,
    validate_customer_rules,
    validate_location_hierarchy,
    validate_submission,
)

ApplicationLinkKind = Literal["internal", "external"]
ApplicationLinkPlanCompiler = Callable[..., FrozenApplicationLinkRoute]
ProgressReporter = Callable[..., None]


def freeze_product_execution_snapshot(
    submission: ProductApplicationSubmission,
    catalog: ProductCatalog,
    *,
    plan_compiler: ApplicationLinkPlanCompiler,
) -> tuple[ProductApplicationSubmission, ProductExecutionSnapshot]:
    payload = deepcopy(submission.payload)
    product = catalog.product(submission.product)
    validate_product_workflow(product.workflow)
    environment = normalize_environment(payload.get("environment"), catalog)
    method = product.method(str(payload.get("applicationMethod") or "") or None)
    payload.update(
        environment=environment,
        product=submission.product,
        applicationMethod=method.code,
    )
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
    plan = plan_compiler(
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
        application_link_route=plan,
    )
    normalized_submission = ProductApplicationSubmission(
        name=submission.name,
        product=submission.product,
        payload=payload,
    )
    validate_submission(normalized_submission, execution_snapshot=snapshot, catalog=catalog)
    return (
        normalized_submission,
        snapshot.model_copy(update={"normalized_payload": deepcopy(normalized_submission.payload)}),
    )


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


def build_product_application_result(
    submission: ProductApplicationSubmission,
    snapshot: ProductExecutionSnapshot,
    *,
    outcome: Mapping[str, Any],
) -> dict[str, Any]:
    preview = outcome["agreementPreview"]
    session = outcome["session"]
    identity_completed = bool(outcome["identityVerificationCompleted"])
    return {
        "validated": True,
        "product": submission.product,
        "productType": snapshot.product_type,
        "customerType": submission.payload["customerType"],
        "switch": snapshot.switch_field,
        "switchEnabled": submission.payload[snapshot.switch_field],
        "executionConfigVersion": snapshot.catalog_version,
        "applicationMethod": snapshot.method_code,
        "executionFields": list(snapshot.fields),
        "message": (
            "申请链接、Session、协议及身份验证完成"
            if identity_completed
            else "申请链接、Session、协议及申请提交完成"
        ),
        "applicationLink": {
            "generated": True,
            "category": outcome["applicationLinkCategory"],
            "selected": outcome["selectedApplicationLinkKind"],
        },
        "agreementReadCompleted": bool(outcome["agreementDocuments"]),
        "identityVerificationCompleted": identity_completed,
        "identityVerification": outcome.get("identityVerification"),
        "agreementTemplates": list(outcome["agreementTemplates"]),
        "agreementPreview": {
            "successFlag": preview["successFlag"],
            "docId": preview.get("docId"),
            "Documents": list(preview["Documents"]),
        },
        "agreementDocuments": list(outcome["agreementDocuments"]),
        "externalSession": {
            "status": session.status.value,
            "established": session.status.value == "established",
            "cookieNames": list(session.cookie_names),
            "forwardedHeaderNames": list(session.header_names),
            "finalUrlPresent": session.final_url is not None,
        },
    }


def submit_product_application(
    submission: ProductApplicationSubmission,
    *,
    idempotency_key: str | None,
    trace_id: str | None,
    timeout_seconds: int,
    plan_compiler: ApplicationLinkPlanCompiler,
) -> CreatedJob:
    prepared_submission, prepared_snapshot = freeze_product_execution_snapshot(
        submission,
        load_product_catalog(),
        plan_compiler=plan_compiler,
    )
    resolved_key, resolved_trace_id = resolve_job_identifiers(idempotency_key, trace_id)
    created = create_job(
        kind="product_application",
        name=prepared_submission.name,
        product=prepared_submission.product,
        payload=prepared_submission.payload,
        trace_id=resolved_trace_id,
        idempotency_key=resolved_key,
        timeout_seconds=timeout_seconds,
        execution_config_version=prepared_snapshot.catalog_version,
        execution_config_snapshot=prepared_snapshot.model_dump(mode="json"),
    )
    if created.created:
        add_business_log(
            created.job,
            "产品申请已受理，等待后台处理",
            step="submitted",
            progress=0,
        )
    return created


def execute_product_application(
    *,
    runtime: Any,
    submission: ProductApplicationSubmission,
    snapshot: ProductExecutionSnapshot,
    application_link_kind: ApplicationLinkKind,
    progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    validate_submission(submission, execution_snapshot=snapshot)
    validate_product_workflow(snapshot.workflow)
    _report(progress, "validate", 25, "产品申请参数校验完成")
    runtime.open()
    try:
        context = WorkflowExecutionContext(
            runtime=runtime,
            snapshot=snapshot,
            payload=submission.payload,
            application_link_kind=application_link_kind,
            progress=progress,
        )
        execute_product_workflow(context)
        application_result = context.require("application", ApplicationModuleOutcome)
        identity_result = context.optional("identity", IdentityModuleOutcome)
    finally:
        runtime.close()
    return build_product_application_result(
        submission,
        snapshot,
        outcome={
            "applicationLinkCategory": application_result.application_link_category,
            "selectedApplicationLinkKind": application_result.selected_application_link_kind,
            "agreementTemplates": application_result.agreement_templates,
            "agreementPreview": application_result.agreement_preview,
            "agreementDocuments": application_result.agreement_documents,
            "session": application_result.session,
            "identityVerificationCompleted": bool(identity_result and identity_result.completed),
            "identityVerification": identity_result.as_api_result() if identity_result else None,
        },
    )


def _report(
    reporter: ProgressReporter | None,
    stage: str,
    progress: int,
    message: str,
) -> None:
    if reporter is not None:
        reporter(stage=stage, progress=progress, message=message)
