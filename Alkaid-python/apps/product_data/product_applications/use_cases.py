from __future__ import annotations

from typing import Any

from apps.jobs.services import CreatedJob, create_job, resolve_job_identifiers
from apps.product_data.catalog import ProductExecutionSnapshot, load_product_catalog
from apps.product_data.product_applications.agreement_use_case import (
    query_preview_and_read_agreements,
)
from apps.product_data.product_applications.application_link_use_case import (
    generate_application_link_and_establish_session,
)
from apps.product_data.product_applications.contracts import (
    AgreementGateway,
    ApplicationLinkGateway,
    ApplicationLinkKind,
    ExternalSessionGateway,
    ProductApplicationRuntime,
    ProgressReporter,
)
from apps.product_data.product_applications.preparation import (
    freeze_product_execution_snapshot,
)
from apps.product_data.product_applications.presenter import build_product_application_result
from apps.product_data.product_applications.results import ProductApplicationOutcome
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.validation import validate_submission


def submit_product_application(
    submission: ProductApplicationSubmission,
    *,
    idempotency_key: str | None,
    trace_id: str | None,
    timeout_seconds: int,
) -> CreatedJob:
    prepared = freeze_product_execution_snapshot(submission, load_product_catalog())
    resolved_key, resolved_trace_id = resolve_job_identifiers(idempotency_key, trace_id)
    return create_job(
        kind="product_application",
        name=prepared.submission.name,
        product=prepared.submission.product,
        payload=prepared.submission.payload,
        trace_id=resolved_trace_id,
        idempotency_key=resolved_key,
        timeout_seconds=timeout_seconds,
        execution_config_version=prepared.snapshot.catalog_version,
        execution_config_snapshot=prepared.snapshot.model_dump(mode="json"),
    )


def execute_product_application(
    *,
    runtime: ProductApplicationRuntime,
    application_links: ApplicationLinkGateway,
    external_session: ExternalSessionGateway,
    agreements: AgreementGateway,
    submission: ProductApplicationSubmission,
    snapshot: ProductExecutionSnapshot,
    application_link_kind: ApplicationLinkKind,
    progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    validate_submission(submission, execution_snapshot=snapshot)
    _report(progress, "validate", 25, "产品申请参数校验完成")

    with runtime:
        application_session = generate_application_link_and_establish_session(
            application_links=application_links,
            external_session=external_session,
            snapshot=snapshot,
            application_link_kind=application_link_kind,
            progress=progress,
        )
        agreement_reading = query_preview_and_read_agreements(
            agreements=agreements,
            external_session=external_session,
            payload=submission.payload,
            progress=progress,
        )

    outcome = ProductApplicationOutcome(
        application_link_category=application_session.application_link_category,
        application_links=application_session.application_links,
        selected_application_link_kind=application_session.selected_application_link_kind,
        agreement_templates=agreement_reading.agreement_templates,
        agreement_preview=agreement_reading.agreement_preview,
        agreement_documents=agreement_reading.agreement_documents,
        session=agreement_reading.session,
    )
    return build_product_application_result(submission, snapshot, outcome=outcome)


def _report(reporter: ProgressReporter | None, stage: str, progress: int, message: str) -> None:
    if reporter is not None:
        reporter(stage=stage, progress=progress, message=message)
