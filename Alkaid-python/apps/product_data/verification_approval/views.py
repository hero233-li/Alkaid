from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.http import submit_async_job
from apps.product_data.verification_approval.schemas import (
    VerificationAction,
    VerificationActionSubmission,
    VerificationItemJobSubmission,
    VerificationItemUpdateSubmission,
    VerificationOperation,
    VerificationSearchSubmission,
    VerificationTaskOperationSubmission,
)
from apps.product_data.verification_approval.services import get_verification_config


@require_GET
def verification_config(request: HttpRequest) -> JsonResponse:
    return api_response(get_verification_config())


@csrf_exempt
@require_POST
def search_verification(request: HttpRequest) -> JsonResponse:
    try:
        submission = VerificationSearchSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"核实审批查询参数无效：{exc}", status=400, code="invalid_submission")
    return _submit_job(
        request,
        operation=VerificationOperation.SEARCH,
        payload=submission.model_dump(mode="json", by_alias=True),
        name=f"核实审批查询-{submission.contract_no}",
    )


@csrf_exempt
@require_POST
def claim_verification(request: HttpRequest, task_id: str) -> JsonResponse:
    try:
        submission = VerificationTaskOperationSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"核实任务上下文无效：{exc}", status=400, code="invalid_submission")
    if submission.context.id != task_id:
        return api_error("核实任务上下文与请求路径不一致", status=400)
    return _submit_job(
        request,
        operation=VerificationOperation.CLAIM,
        payload=submission.model_dump(mode="json", by_alias=True),
        name=f"核实审批领取-{task_id}",
    )


@csrf_exempt
@require_POST
def return_verification(request: HttpRequest, task_id: str) -> JsonResponse:
    try:
        submission = VerificationTaskOperationSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"核实任务上下文无效：{exc}", status=400, code="invalid_submission")
    if submission.context.id != task_id:
        return api_error("核实任务上下文与请求路径不一致", status=400)
    return _submit_job(
        request,
        operation=VerificationOperation.RETURN,
        payload=submission.model_dump(mode="json", by_alias=True),
        name=f"核实审批退回-{task_id}",
    )


@csrf_exempt
@require_POST
def refresh_verification(request: HttpRequest, task_id: str) -> JsonResponse:
    try:
        submission = VerificationTaskOperationSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"核实任务上下文无效：{exc}", status=400, code="invalid_submission")
    if submission.context.id != task_id:
        return api_error("核实任务上下文与请求路径不一致", status=400)
    return _submit_job(
        request,
        operation=VerificationOperation.REFRESH,
        payload=submission.model_dump(mode="json", by_alias=True),
        name=f"核实审批刷新-{task_id}",
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
        return api_error(f"核实项参数无效：{exc}", status=400, code="invalid_submission")
    if submission.context.id != task_id:
        return api_error("核实任务上下文与请求路径不一致", status=400)
    job_submission = VerificationItemJobSubmission(
        status=submission.status,
        context=submission.context,
        context_proof=submission.context_proof,
        item_id=item_id,
    )
    return _submit_job(
        request,
        operation=VerificationOperation.ITEM_UPDATE,
        payload=job_submission.model_dump(mode="json", by_alias=True),
        name=f"核实审批项目更新-{task_id}-{item_id}",
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
        return api_error(f"核实审批操作上下文无效：{exc}", status=400, code="invalid_submission")
    except ValueError:
        return api_error("核实审批操作无效", status=400)
    if submission.action != parsed_action.value:
        return api_error("核实审批操作与请求路径不一致", status=400)
    if submission.context.id != task_id:
        return api_error("核实任务上下文与请求路径不一致", status=400)
    return _submit_job(
        request,
        operation=VerificationOperation.ACTION,
        payload=submission.model_dump(mode="json", by_alias=True),
        name=f"核实审批操作-{task_id}-{parsed_action.value}",
    )


def _submit_job(
    request: HttpRequest,
    *,
    operation: VerificationOperation,
    payload: dict[str, object],
    name: str,
) -> JsonResponse:
    return submit_async_job(
        request,
        kind="verification_approval",
        name=name,
        product="verification-approval",
        payload={"operation": operation.value, "data": payload},
        timeout_seconds=settings.VERIFICATION_APPROVAL_TIMEOUT_SECONDS,
        snapshot={"operation": operation.value, "version": 1},
    )
