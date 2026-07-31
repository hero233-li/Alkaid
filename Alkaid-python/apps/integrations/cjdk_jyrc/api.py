from apps.integrations.contracts import EndpointSpec, RetryMode
from apps.integrations.cjdk_jyrc.models import (
    AgreementDocumentEnvelope,
    AgreementPreviewEnvelope,
    QueryAgreementEnvelope,
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
