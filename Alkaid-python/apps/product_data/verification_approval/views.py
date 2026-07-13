import time
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.integrations.contracts import BusinessResponseError
from apps.integrations.http import ExternalServiceError
from apps.jobs.services import resolve_job_identifiers
from apps.product_data.verification_approval.schemas import (
    VerificationAction,
    VerificationActionSubmission,
    VerificationItemUpdateSubmission,
    VerificationSearchSubmission,
    VerificationTaskOperationSubmission,
)
from apps.product_data.verification_approval.services import (
    apply_verification_action,
    claim_verification_task,
    get_verification_config,
    return_verification_task,
    search_verification_task,
    update_verification_item,
)


@require_GET
def verification_config(request: HttpRequest) -> JsonResponse:
    _debug_delay()
    return api_response(get_verification_config())


@csrf_exempt
@require_POST
def search_verification(request: HttpRequest) -> JsonResponse:
    _debug_delay()
    try:
        submission = VerificationSearchSubmission.model_validate_json(request.body)
        trace_id = _trace_id(request)
        return api_response(search_verification_task(submission, trace_id=trace_id))
    except (ValidationError, ValueError) as exc:
        return api_error(f"核实审批查询参数无效：{exc}", status=400)
    except (ExternalServiceError, BusinessResponseError) as exc:
        return api_error(f"核实审批外系统调用失败：{exc}", status=502)


@csrf_exempt
@require_POST
def claim_verification(request: HttpRequest, task_id: str) -> JsonResponse:
    try:
        submission = VerificationTaskOperationSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"核实任务上下文无效：{exc}", status=400)
    return _run_external(
        request,
        lambda trace_id: claim_verification_task(
            task_id,
            submission.context,
            trace_id=trace_id,
        ),
    )


@csrf_exempt
@require_POST
def return_verification(request: HttpRequest, task_id: str) -> JsonResponse:
    try:
        submission = VerificationTaskOperationSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"核实任务上下文无效：{exc}", status=400)
    return _run_external(
        request,
        lambda trace_id: return_verification_task(
            task_id,
            submission.context,
            trace_id=trace_id,
        ),
    )


@csrf_exempt
@require_POST
def update_verification_item_status(
    request: HttpRequest,
    task_id: str,
    item_id: str,
) -> JsonResponse:
    try:
        submission = VerificationItemUpdateSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"核实项参数无效：{exc}", status=400)
    return _run_external(
        request,
        lambda trace_id: update_verification_item(
            task_id,
            item_id,
            submission.status,
            submission.context,
            trace_id=trace_id,
        ),
    )


@csrf_exempt
@require_POST
def submit_verification_action(
    request: HttpRequest,
    task_id: str,
    action: str,
) -> JsonResponse:
    try:
        parsed_action = VerificationAction(action)
        submission = VerificationActionSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"核实审批操作上下文无效：{exc}", status=400)
    except ValueError:
        return api_error("核实审批操作无效", status=400)
    if submission.action != parsed_action.value:
        return api_error("核实审批操作与请求路径不一致", status=400)
    return _run_external(
        request,
        lambda trace_id: apply_verification_action(
            task_id,
            parsed_action,
            submission.context,
            trace_id=trace_id,
        ),
    )


def _trace_id(request: HttpRequest) -> str:
    return resolve_job_identifiers(None, request.headers.get("X-Trace-ID"))[1]


def _run_external(
    request: HttpRequest,
    operation: Callable[[str], dict[str, Any]],
) -> JsonResponse:
    _debug_delay()
    try:
        return api_response(operation(_trace_id(request)))
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except (ExternalServiceError, BusinessResponseError) as exc:
        return api_error(f"核实审批外系统调用失败：{exc}", status=502)


def _debug_delay() -> None:
    delay_seconds = max(0.0, settings.VERIFICATION_APPROVAL_DEBUG_DELAY_SECONDS)
    if delay_seconds:
        time.sleep(delay_seconds)
