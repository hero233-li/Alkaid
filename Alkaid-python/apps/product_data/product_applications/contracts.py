from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ApplicationLinkCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    plan: dict[str, Any]
    normalized_payload: dict[str, Any]


class ApplicationLinksResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    internal_url: str = Field(min_length=1)
    external_url: str = Field(min_length=1)


class SessionStatus(str, Enum):
    NOT_STARTED = "not_started"
    PAGE_OPENED = "page_opened"
    PARTIAL = "partial"
    ESTABLISHED = "established"
    FAILED = "failed"


class SessionState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SessionStatus = SessionStatus.NOT_STARTED
    cookie_names: tuple[str, ...] = ()
    header_names: tuple[str, ...] = ()
    final_url: str | None = None
    missing_cookies: tuple[str, ...] = ()
    missing_headers: tuple[str, ...] = ()
    missing_any_headers: tuple[str, ...] = ()


class AgreementTemplateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_id: str
    doc_name: str | None = None
    doc_type: str | None = None
    fcos_template_no: str | None = None
    status: str | None = None


class AgreementPreviewDocumentResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_id: str
    doc_name: str | None = None
    doc_type: str | None = None
    fcos_template_no: str | None = None


class AgreementPreviewResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    success_flag: str
    doc_id: str | None = None
    documents: tuple[AgreementPreviewDocumentResult, ...] = ()


class AgreementDocumentResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_id: str
    file_name: str | None = None
    declared_size: str | None = None
    success_flag: str
    content_bytes: int | None = None


class ProductApplicationPort(Protocol):
    def __enter__(self) -> ProductApplicationPort: ...

    def __exit__(self, *args: object) -> None: ...

    def generate_application_link(
        self, command: ApplicationLinkCommand
    ) -> ApplicationLinksResult: ...

    def initialize_session(self, application_url: str) -> SessionState: ...

    def query_agreement_templates(
        self, payload: Mapping[str, Any]
    ) -> tuple[AgreementTemplateResult, ...]: ...

    def query_agreement_preview(
        self,
        payload: Mapping[str, Any],
        templates: tuple[AgreementTemplateResult, ...],
    ) -> AgreementPreviewResult: ...

    def read_agreement_document(self, doc_id: str) -> AgreementDocumentResult: ...

    def session_state(self) -> SessionState: ...
