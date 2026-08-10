from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from apps.utils.product_Conf.catalog import ProductExecutionSnapshot
from apps.workflow.product_applications.cjdk.runtime import ProductApplicationRuntime
from apps.workflow.product_applications.contracts import SubmittedApplication
from apps.workflow.product_applications.loan_application.application import execute_application

ApplicationLinkKind = Literal["internal", "external"]
ProgressReporter = Callable[..., None]


@dataclass(frozen=True, slots=True)
class ApplicationModuleOutcome:
    """Everything produced by link, session, agreement and submission processing."""

    application_link_category: str
    selected_application_link_kind: ApplicationLinkKind
    agreement_templates: tuple[dict[str, Any], ...]
    agreement_preview: Mapping[str, Any]
    agreement_documents: tuple[dict[str, Any], ...]
    session: Any
    submitted_application: SubmittedApplication


def execute_application_module(
    *,
    runtime: ProductApplicationRuntime,
    snapshot: ProductExecutionSnapshot,
    payload: Mapping[str, Any],
    application_link_kind: ApplicationLinkKind,
    progress: ProgressReporter | None = None,
) -> ApplicationModuleOutcome:
    """Open the application, establish its session, read agreements and submit it."""

    result = execute_application(
        client=runtime.client,
        settings=runtime.settings,
        observer=runtime.observer,
        trace_id=runtime.trace_id,
        snapshot=snapshot,
        payload=payload,
        application_link_kind=application_link_kind,
        progress=progress,
    )
    return ApplicationModuleOutcome(
        application_link_category=str(result["applicationLinkCategory"]),
        selected_application_link_kind=application_link_kind,
        agreement_templates=tuple(result["agreementTemplates"]),
        agreement_preview=result["agreementPreview"],
        agreement_documents=tuple(result["agreementDocuments"]),
        session=result["session"],
        submitted_application=result["submittedApplication"],
    )
