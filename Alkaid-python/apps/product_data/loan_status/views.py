import json

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.http import submit_async_job
from apps.product_data.loan_status.schemas import (
    LoanAction,
    LoanActionSubmission,
    LoanSearchSubmission,
    LoanStatusOperation,
)
from apps.product_data.loan_status.services import get_loan_status_config


@require_GET
def loan_status_config(request: HttpRequest) -> JsonResponse:
    del request
    return api_response(get_loan_status_config())


@csrf_exempt
@require_POST
def search_loans(request: HttpRequest) -> JsonResponse:
    try:
        submission = LoanSearchSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"贷款状态查询参数无效：{exc}", status=400)
    return _submit_job(
        request,
        LoanStatusOperation.SEARCH,
        submission.model_dump(mode="json", by_alias=True),
        "贷款状态查询",
    )


@csrf_exempt
@require_POST
def apply_loan_action(request: HttpRequest, contract_no: str, action: str) -> JsonResponse:
    try:
        parsed_action = LoanAction(action)
        raw = json.loads(request.body.decode("utf-8") or "{}")
        if not isinstance(raw, dict):
            raise ValueError("请求体必须为对象")
        submission = LoanActionSubmission.model_validate(
            {**raw, "action": parsed_action.value, "contractNo": contract_no}
        )
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return api_error(f"贷款状态操作参数无效：{exc}", status=400)
    return _submit_job(
        request,
        LoanStatusOperation.ACTION,
        submission.model_dump(mode="json", by_alias=True, exclude_none=True),
        f"贷款状态操作-{parsed_action.value}",
    )


def _submit_job(
    request: HttpRequest, operation: LoanStatusOperation, payload: dict[str, object], name: str
) -> JsonResponse:
    return submit_async_job(
        request,
        kind="loan_status",
        name=name,
        product="loan-status",
        payload={"operation": operation.value, "data": payload},
        timeout_seconds=settings.LOAN_STATUS_TIMEOUT_SECONDS,
        snapshot={"operation": operation.value, "version": 1},
    )
