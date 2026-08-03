from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

ApplicationLinkKind = Literal["internal", "external"]


class ProgressReporter(Protocol):
    def __call__(self, *, stage: str, progress: int, message: str) -> None: ...


class ApplicationLinkCategory(str, Enum):
    SUN_CODE = "SUN_CODE"
    DYNAMIC_LINK = "DYNAMIC_LINK"

    @property
    def display_name(self) -> str:
        return {
            ApplicationLinkCategory.SUN_CODE: "太阳码",
            ApplicationLinkCategory.DYNAMIC_LINK: "动态链接",
        }[self]


class FrozenApplicationLinkRoute(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route_id: str = Field(min_length=1, max_length=255)
    environment: str = Field(min_length=1, max_length=128)
    application_methods: tuple[str, ...] = Field(min_length=1)
    category_code: ApplicationLinkCategory
    integration_profile_id: str = Field(min_length=1, max_length=255)
    integration_profile_version: int = Field(ge=1)
    integration_profile_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    required_fields: tuple[str, ...]
    compiled_request_template: dict[str, Any]
    payload_bindings: dict[str, str]
    secret_bindings: dict[str, str]


class CompiledApplicationLinkPlan(FrozenApplicationLinkRoute):
    def freeze(self) -> FrozenApplicationLinkRoute:
        return FrozenApplicationLinkRoute.model_validate(self.model_dump(mode="python"))


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


class ProductApplicationRuntime(Protocol):
    """Own only the lifetime of shared external infrastructure."""

    def __enter__(self) -> ProductApplicationRuntime: ...

    def __exit__(self, *args: object) -> None: ...


class ApplicationLinkGateway(Protocol):
    def generate_application_link(
        self, command: ApplicationLinkCommand
    ) -> ApplicationLinksResult: ...


class ExternalSessionGateway(Protocol):
    def initialize_session(self, application_url: str) -> SessionState: ...

    def session_state(self) -> SessionState: ...


class AgreementGateway(Protocol):
    def query_agreement_templates(
        self, payload: Mapping[str, Any]
    ) -> tuple[AgreementTemplateResult, ...]: ...

    def query_agreement_preview(
        self,
        payload: Mapping[str, Any],
        templates: tuple[AgreementTemplateResult, ...],
    ) -> AgreementPreviewResult: ...

    def read_agreement_documents(
        self, doc_ids: tuple[str, ...]
    ) -> tuple[AgreementDocumentResult, ...]: ...
