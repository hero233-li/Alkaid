import time

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.dispatch import enqueue_job
from apps.jobs.services import JobConflict, create_job, resolve_job_identifiers, serialize_job
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
    _debug_delay()
    return api_response(get_verification_config())


@csrf_exempt
@require_POST
def search_verification(request: HttpRequest) -> JsonResponse:
    try:
        submission = VerificationSearchSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"核实审批查询参数无效：{exc}", status=400)
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
        return api_error(f"核实任务上下文无效：{exc}", status=400)
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
        return api_error(f"核实任务上下文无效：{exc}", status=400)
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
        return api_error(f"核实任务上下文无效：{exc}", status=400)
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
        return api_error(f"核实项参数无效：{exc}", status=400)
    if submission.context.id != task_id:
        return api_error("核实任务上下文与请求路径不一致", status=400)
    job_submission = VerificationItemJobSubmission(
        status=submission.status,
        context=submission.context,
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
        return api_error(f"核实审批操作上下文无效：{exc}", status=400)
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
    try:
        idempotency_key, trace_id = resolve_job_identifiers(
            request.headers.get("X-Idempotency-Key"),
            request.headers.get("X-Trace-ID"),
        )
        created = create_job(
            kind=f"verification_approval.{operation.value}",
            name=name,
            product="verification-approval",
            payload=payload,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            timeout_seconds=settings.VERIFICATION_APPROVAL_TIMEOUT_SECONDS,
            execution_config_version=1,
            execution_config_snapshot={"operation": operation.value, "version": 1},
        )
    except JobConflict as exc:
        return api_error(str(exc), status=409)
    except ValueError as exc:
        return api_error(str(exc), status=400)
    if created.created:
        transaction.on_commit(lambda: enqueue_job(created.job))
    return api_response(serialize_job(created.job), status=202 if created.created else 200)


def _debug_delay() -> None:
    delay_seconds = max(0.0, settings.VERIFICATION_APPROVAL_DEBUG_DELAY_SECONDS)
    if delay_seconds:
        time.sleep(delay_seconds)
