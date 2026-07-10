from typing import Any

from apps.integrations.mock_product.builders.common import req_body_envelope
from apps.integrations.mock_product.models import ProductSubmissionInput, RequestHead


def build_product_apply_form(
    head: RequestHead,
    request: ProductSubmissionInput,
) -> dict[str, Any]:
    return req_body_envelope(
        {
            "cooperatorId": "JLHB",
            "cooperatorName": "吉农e贷",
            "custNme": request.customer_name,
            "distId": "220102",
            "flowId": "JLHB100507",
            "idtyNo": request.certificate_no,
            "loanFlowStag": "1",
            "orderNo": request.order_no or _default_order_no(head),
            "selblProdId": "CJDK-JLHB",
            "gbIndsTpCd": "A0143",
            "spclCdtPolcyFlg": "02",
            "loanPurpSubCatgCd": "26",
            "thdptyCallbackUrlAddr": (
                "https://stage-m.loan.cacfintech.com/#/app/success-page"
            ),
        },
        app_id="appohjkk1202307100001",
        env="UATC",
    )


def _default_order_no(head: RequestHead) -> str:
    return f"{head.starttime[:12]}{head.traceno[:6].upper()}"
