from dataclasses import dataclass, field
from typing import Any

from apps.integrations.cjdk_jyrc.models import (
    AgreementDocumentBody,
    AgreementPreviewData,
    AgreementTemplateInfo,
    ApplicationLinks,
)
from apps.jobs.models import Job
from apps.product_data.catalog import ProductExecutionSnapshot
from apps.product_data.product_applications.schemas import ProductApplicationSubmission


@dataclass
class ProductApplicationContext:
    """Data shared by the code-ordered product-application flow."""

    job: Job
    submission: ProductApplicationSubmission | None = None
    execution_snapshot: ProductExecutionSnapshot | None = None

    application_link_category: str | None = None
    application_links: ApplicationLinks | None = None
    selected_application_link_kind: str | None = None

    agreement_templates: list[AgreementTemplateInfo] = field(default_factory=list)
    agreement_preview: AgreementPreviewData | None = None
    agreement_documents: list[AgreementDocumentBody] = field(default_factory=list)

    session_established: bool = False
    session_cookie_names: tuple[str, ...] = ()
    session_header_names: tuple[str, ...] = ()
    session_final_url: str | None = None

    result: dict[str, Any] | None = None
