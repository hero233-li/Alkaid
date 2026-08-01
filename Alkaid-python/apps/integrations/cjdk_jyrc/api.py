from apps.integrations.cjdk_jyrc.models import (
    AgreementDocumentEnvelope,
    AgreementPreviewEnvelope,
    QueryAgreementEnvelope,
)
from apps.integrations.contracts import EndpointSpec, RetryMode

QUERY_AGREEMENT_TEMPLATES = EndpointSpec(
    operation_id="cjdk_jyrc.query_agreement_templates",
    method="POST",
    path="/h5/microservice/queryAgreementTemplateInfoListEA.do",
    response_model=QueryAgreementEnvelope,
    retry_mode=RetryMode.NEVER,
)

QUERY_PREVIEW_IMAGE = EndpointSpec(
    operation_id="cjdk_jyrc.query_preview_image",
    method="POST",
    path="/h5/microservice/queryPreviewImage.ajax",
    response_model=AgreementPreviewEnvelope,
    retry_mode=RetryMode.NEVER,
)

SHOW_DOCUMENT_BY_DOC_ID = EndpointSpec(
    operation_id="cjdk_jyrc.show_document_by_doc_id",
    method="POST",
    path="/h5/microservice/showDocumentByDocIdList.ajax",
    response_model=AgreementDocumentEnvelope,
    retry_mode=RetryMode.NEVER,
)

AGREEMENT_ENDPOINTS = (
    QUERY_AGREEMENT_TEMPLATES,
    QUERY_PREVIEW_IMAGE,
    SHOW_DOCUMENT_BY_DOC_ID,
)
