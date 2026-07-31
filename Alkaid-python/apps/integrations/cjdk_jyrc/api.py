from apps.integrations.contracts import EndpointSpec, RetryMode
from apps.integrations.cjdk_jyrc.models import (
    AgreementDocumentEnvelope,
    AgreementPreviewEnvelope,
    GenerateApplicationLinkEnvelope,
    QueryAgreementEnvelope,
)


CREATE_SUN_CODE_LINK = EndpointSpec(
    operation_id="cjdk_jyrc.generate_sun_code_link",
    method="POST",
    path="/links/sun-code",
    response_model=GenerateApplicationLinkEnvelope,
    success_path="code",
    success_values=("0000",),
)

CREATE_DYNAMIC_LINK = EndpointSpec(
    operation_id="cjdk_jyrc.generate_dynamic_link",
    method="POST",
    path="/links/dynamic",
    response_model=GenerateApplicationLinkEnvelope,
    success_path="code",
    success_values=("0000",),
)

QUERY_AGREEMENT_TEMPLATES = EndpointSpec(
    operation_id="cjdk_jyrc.query_agreement_templates",
    method="POST",
    path="/h5/microservice/queryAgreementTemplateInfoListEA.do",
    response_model=QueryAgreementEnvelope,
    retry_mode=RetryMode.SAFE,
)

QUERY_PREVIEW_IMAGE = EndpointSpec(
    operation_id="cjdk_jyrc.query_preview_image",
    method="POST",
    path="/h5/microservice/queryPreviewImage.ajax",
    response_model=AgreementPreviewEnvelope,
    retry_mode=RetryMode.SAFE,
)

SHOW_DOCUMENT_BY_DOC_ID = EndpointSpec(
    operation_id="cjdk_jyrc.show_document_by_doc_id",
    method="POST",
    path="/h5/microservice/showDocumentByDocIdList.ajax",
    response_model=AgreementDocumentEnvelope,
    retry_mode=RetryMode.SAFE,
)

AGREEMENT_ENDPOINTS = (
    QUERY_AGREEMENT_TEMPLATES,
    QUERY_PREVIEW_IMAGE,
    SHOW_DOCUMENT_BY_DOC_ID,
)
