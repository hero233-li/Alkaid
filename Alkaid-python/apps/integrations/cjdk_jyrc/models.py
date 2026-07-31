from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CjdkResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ApplicationLinks(CjdkResponseModel):
    internal_url: str = Field(
        min_length=1,
        validation_alias=AliasChoices("internal_url", "internalUrl"),
    )
    external_url: str = Field(
        min_length=1,
        validation_alias=AliasChoices("external_url", "externalUrl"),
    )


class GenerateApplicationLinkRequest(BaseModel):
    """Product-local request passed to the Java SDK as one JSON object."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    env: str = Field(min_length=1)
    product: str = Field(min_length=1)
    category: str = Field(min_length=1)
    cooperation_project_id: str | None = Field(
        default=None,
        alias="cooperationProjectId",
        validation_alias=AliasChoices(
            "cooperation_project_id",
            "cooperationProjectId",
            "projectId",
        ),
    )
    payload: dict[str, Any]

    def external_request(self) -> dict[str, Any]:
        content: dict[str, Any] = {
            "env": self.env,
            "product": self.product,
            "category": self.category,
            "payload": self.payload,
        }
        if self.cooperation_project_id:
            content["cooperationProjectId"] = self.cooperation_project_id
        return content


class GenerateApplicationLinkEnvelope(CjdkResponseModel):
    """Legacy HTTP envelope retained only for backwards-compatible imports."""

    code: str
    message: str | None = None
    data: ApplicationLinks


class AgreementTemplateInfo(CjdkResponseModel):
    doc_id: str = Field(alias="docId")
    doc_name: str | None = Field(default=None, alias="docName")
    doc_type: str | None = Field(default=None, alias="docType")
    fcos_template_no: str | None = Field(default=None, alias="fcosTemplateNo")
    status: str | None = None
    original_doc_id: str | None = Field(default=None, alias="originalDocId")
    org_code: str | None = Field(default=None, alias="orgCode")


class QueryAgreementData(CjdkResponseModel):
    templates: list[AgreementTemplateInfo] = Field(
        default_factory=list,
        alias="docAgreementTemplateInfoList",
    )


class QueryAgreementBody(CjdkResponseModel):
    request: dict[str, Any] | None = None
    process_status_code: str | None = Field(default=None, alias="processStatusCode")
    response: QueryAgreementData


class QueryAgreementEnvelope(CjdkResponseModel):
    rsp_body: QueryAgreementBody = Field(alias="RSP_BODY")


class AgreementPreviewDocument(CjdkResponseModel):
    doc_id: str = Field(alias="docId")
    doc_name: str | None = Field(default=None, alias="docName")
    doc_type: str | None = Field(default=None, alias="docType")
    fcos_template_no: str | None = Field(default=None, alias="fcosTemplateNo")
    business_no: str | None = Field(default=None, alias="businessNo")
    channel: str | None = None


class AgreementPreviewData(CjdkResponseModel):
    success_flag: str = Field(alias="successFlag")
    message: str | None = None
    doc_id: str | None = Field(default=None, alias="docId")
    documents: list[AgreementPreviewDocument] = Field(default_factory=list, alias="docList")
    image_preview_new_switch: str | None = Field(
        default=None,
        alias="imagePreviewNewSwitch",
    )
    loan_product_line: str | None = Field(default=None, alias="loanProdLine")
    is_external_agencies: str | None = Field(default=None, alias="isExternalAgencies")


class AgreementPreviewBody(CjdkResponseModel):
    request: dict[str, Any] | None = None
    response: AgreementPreviewData


class AgreementPreviewEnvelope(CjdkResponseModel):
    rsp_body: AgreementPreviewBody = Field(alias="RSP_BODY")
    rsp_head: dict[str, Any] | None = Field(default=None, alias="RSP_HEAD")


class AgreementFileInfo(CjdkResponseModel):
    file_name: str | None = Field(default=None, alias="fileName")
    down_file: str | None = Field(default=None, alias="downFile")
    resource_object_date: str | None = Field(default=None, alias="resourceObjectDT")
    resource_object_position: str | None = Field(
        default=None,
        alias="resourceObjectPosition",
    )
    resource_object_version: str | None = Field(
        default=None,
        alias="resourceObjectVers",
    )
    resource_object_serial_no: str | None = Field(
        default=None,
        alias="resourceObjectSN",
    )
    url: str | None = None


class AgreementDocumentBody(CjdkResponseModel):
    request: dict[str, Any] | None = None
    down_file: str | None = Field(default=None, alias="downFile")
    file_info: list[AgreementFileInfo] = Field(default_factory=list, alias="fileInfo")
    doc_size: str | None = Field(default=None, alias="docSize")
    is_external_agencies: str | None = Field(default=None, alias="isExternalAgencies")
    success_flag: str = Field(alias="successFlag")


class AgreementDocumentEnvelope(CjdkResponseModel):
    rsp_body: AgreementDocumentBody = Field(alias="RSP_BODY")
    rsp_head: dict[str, Any] | None = Field(default=None, alias="RSP_HEAD")
