from dataclasses import dataclass, field
from typing import Any

from apps.integrations.cjdk_jyrc.models import (
    AgreementDocumentBody,
    AgreementPreviewData,
    AgreementTemplateInfo,
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
    agreement_templates: list[AgreementTemplateInfo] = field(default_factory=list)
    agreement_preview: AgreementPreviewData | None = None
    agreement_documents: list[AgreementDocumentBody] = field(default_factory=list)
    session_established: bool = False
    session_header_names: tuple[str, ...] = ()
    result: dict[str, Any] | None = None
