import json
from uuid import UUID

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.workflows.models import WorkflowRun
from apps.workflows.schemas import (
    WorkflowAcceptedResponse,
    WorkflowContext,
    WorkflowStartRequest,
    WorkflowStatusResponse,
)
from apps.workflows.services import IdempotencyConflict, WorkflowRepository
from apps.workflows.tasks import execute_workflow


def error_response(code: str, message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


@require_POST
def start_workflow(request: HttpRequest) -> JsonResponse:
    try:
        payload = WorkflowStartRequest.model_validate_json(request.body)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return error_response("invalid_request", str(exc), 400)

    try:
        created = WorkflowRepository.create(payload)
    except IdempotencyConflict as exc:
        return error_response("idempotency_conflict", str(exc), 409)
    if created.created:
        transaction.on_commit(lambda: execute_workflow.delay(str(created.run.id)))

    response = WorkflowAcceptedResponse(
        workflow_id=created.run.id,
        status=created.run.status,
        created=created.created,
    )
    return JsonResponse(response.model_dump(mode="json"), status=202 if created.created else 200)


@require_GET
def workflow_status(request: HttpRequest, workflow_id: UUID) -> JsonResponse:
    try:
        run = WorkflowRun.objects.get(id=workflow_id)
    except WorkflowRun.DoesNotExist:
        return error_response("not_found", "workflow does not exist", 404)

    response = WorkflowStatusResponse(
        workflow_id=run.id,
        status=run.status,
        current_step=run.current_step,
        context=WorkflowContext.model_validate(run.context),
        error=run.error or None,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
    return JsonResponse(response.model_dump(mode="json"))
