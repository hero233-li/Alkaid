from dataclasses import dataclass, field
from typing import Any

from apps.product_data.catalog import ProductExecutionSnapshot
from apps.product_data.product_applications.contracts import (
    AgreementDocumentResult,
    AgreementPreviewResult,
    AgreementTemplateResult,
    ApplicationLinksResult,
    SessionState,
)
from apps.product_data.product_applications.schemas import ProductApplicationSubmission


@dataclass
class ProductApplicationContext:
    job_id: int
    trace_id: str
    submission: ProductApplicationSubmission
    execution_snapshot: ProductExecutionSnapshot
    application_link_category: str | None = None
    application_links: ApplicationLinksResult | None = None
    selected_application_link_kind: str | None = None
    agreement_templates: tuple[AgreementTemplateResult, ...] = ()
    agreement_preview: AgreementPreviewResult | None = None
    agreement_documents: list[AgreementDocumentResult] = field(default_factory=list)
    session: SessionState = field(default_factory=SessionState)
    result: dict[str, Any] | None = None
