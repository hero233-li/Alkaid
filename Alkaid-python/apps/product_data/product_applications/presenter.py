from typing import Any

from apps.product_data.catalog import ProductExecutionSnapshot
from apps.product_data.product_applications.results import ProductApplicationOutcome
from apps.product_data.product_applications.schemas import ProductApplicationSubmission


def build_product_application_result(
    submission: ProductApplicationSubmission,
    snapshot: ProductExecutionSnapshot,
    *,
    outcome: ProductApplicationOutcome,
) -> dict[str, Any]:
    preview = outcome.agreement_preview
    return {
        "validated": True,
        "product": submission.product,
        "productType": snapshot.product_type,
        "customerType": submission.payload["customerType"],
        "switch": snapshot.switch_field,
        "switchEnabled": submission.payload[snapshot.switch_field],
        "executionConfigVersion": snapshot.catalog_version,
        "applicationMethod": snapshot.method_code,
        "executionFields": list(snapshot.fields),
        "message": "申请链接、Session、协议查询、预览与阅读完成",
        "applicationLink": {
            "generated": True,
            "category": outcome.application_link_category,
            "selected": outcome.selected_application_link_kind,
        },
        "agreementReadCompleted": bool(outcome.agreement_documents),
        "agreementTemplates": [
            {
                "docId": item.doc_id,
                "docName": item.doc_name,
                "docType": item.doc_type,
                "fcosTemplateNo": item.fcos_template_no,
                "status": item.status,
            }
            for item in outcome.agreement_templates
        ],
        "agreementPreview": {
            "successFlag": preview.success_flag,
            "docId": preview.doc_id,
            "documents": [
                {
                    "docId": item.doc_id,
                    "docName": item.doc_name,
                    "docType": item.doc_type,
                    "fcosTemplateNo": item.fcos_template_no,
                }
                for item in preview.documents
            ],
        },
        "agreementDocuments": [
            {
                "docId": item.doc_id,
                "fileName": item.file_name,
                "docSize": item.declared_size,
                "successFlag": item.success_flag,
                "contentBytes": item.content_bytes,
            }
            for item in outcome.agreement_documents
        ],
        "externalSession": {
            "status": outcome.session.status.value,
            "established": outcome.session.status.value == "established",
            "cookieNames": list(outcome.session.cookie_names),
            "forwardedHeaderNames": list(outcome.session.header_names),
            "finalUrlPresent": outcome.session.final_url is not None,
        },
    }
