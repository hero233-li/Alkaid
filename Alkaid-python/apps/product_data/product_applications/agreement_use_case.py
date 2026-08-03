from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.product_data.product_applications.contracts import (
    AgreementGateway,
    ExternalSessionGateway,
    ProgressReporter,
)
from apps.product_data.product_applications.results import AgreementReadingOutcome


def query_preview_and_read_agreements(
    *,
    agreements: AgreementGateway,
    external_session: ExternalSessionGateway,
    payload: Mapping[str, Any],
    progress: ProgressReporter | None = None,
) -> AgreementReadingOutcome:
    templates = agreements.query_agreement_templates(payload)
    _report(progress, "agreement_query", 65, "协议模板查询完成")
    preview = agreements.query_agreement_preview(payload, templates)
    _report(progress, "agreement_preview", 78, "协议预览生成完成")
    documents = agreements.read_agreement_documents(
        tuple(document.doc_id for document in preview.documents)
    )
    session = external_session.session_state()
    _report(progress, "agreement_read", 90, "协议阅读完成，正在保存结果")
    return AgreementReadingOutcome(
        agreement_templates=templates,
        agreement_preview=preview,
        agreement_documents=documents,
        session=session,
    )


def _report(reporter: ProgressReporter | None, stage: str, progress: int, message: str) -> None:
    if reporter is not None:
        reporter(stage=stage, progress=progress, message=message)
