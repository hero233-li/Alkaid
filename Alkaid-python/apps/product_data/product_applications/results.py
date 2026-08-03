from __future__ import annotations

from dataclasses import dataclass

from apps.product_data.catalog import ProductExecutionSnapshot
from apps.product_data.product_applications.contracts import (
    AgreementDocumentResult,
    AgreementPreviewResult,
    AgreementTemplateResult,
    ApplicationLinkKind,
    ApplicationLinksResult,
    SessionState,
)
from apps.product_data.product_applications.schemas import ProductApplicationSubmission


@dataclass(frozen=True)
class PreparedProductApplication:
    submission: ProductApplicationSubmission
    snapshot: ProductExecutionSnapshot


@dataclass(frozen=True)
class ApplicationSessionOutcome:
    application_link_category: str
    application_links: ApplicationLinksResult
    selected_application_link_kind: ApplicationLinkKind
    session: SessionState


@dataclass(frozen=True)
class AgreementReadingOutcome:
    agreement_templates: tuple[AgreementTemplateResult, ...]
    agreement_preview: AgreementPreviewResult
    agreement_documents: tuple[AgreementDocumentResult, ...]
    session: SessionState


@dataclass(frozen=True)
class ProductApplicationOutcome:
    application_link_category: str
    application_links: ApplicationLinksResult
    selected_application_link_kind: ApplicationLinkKind
    agreement_templates: tuple[AgreementTemplateResult, ...]
    agreement_preview: AgreementPreviewResult
    agreement_documents: tuple[AgreementDocumentResult, ...]
    session: SessionState
