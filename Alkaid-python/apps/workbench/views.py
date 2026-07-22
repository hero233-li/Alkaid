from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.workbench.models import WorkbenchHistory
from apps.workbench.schemas import RenameHistorySubmission, WorkbenchRequest
from apps.workbench.services import execute_request, serialize_history


def _invalid(exc: Exception) -> JsonResponse:
    return api_error(f"接口工作台参数无效：{exc}", status=400, code="invalid_submission")


def _disabled() -> JsonResponse | None:
    if getattr(settings, "WORKBENCH_ENABLED", settings.DEBUG):
        return None
    return api_error("当前部署未启用接口工作台", status=404, code="feature_disabled")


@csrf_exempt
@require_http_methods(["POST"])
def execute(request: HttpRequest) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    try:
        submission = WorkbenchRequest.model_validate_json(request.body)
    except ValidationError as exc:
        return _invalid(exc)
    return api_response(execute_request(submission))


@csrf_exempt
@require_http_methods(["POST"])
def execute_multipart(request: HttpRequest) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    try:
        submission = WorkbenchRequest.model_validate_json(request.POST.get("payload", ""))
    except ValidationError as exc:
        return _invalid(exc)
    return api_response(execute_request(submission, request.FILES))


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def history(request: HttpRequest) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    if request.method == "DELETE":
        WorkbenchHistory.objects.all().delete()
        return api_response(None)
    try:
        limit = min(max(int(request.GET.get("limit", "80")), 1), 200)
    except ValueError:
        return api_error("limit 必须是整数", status=400, code="invalid_submission")
    return api_response(
        [serialize_history(item) for item in WorkbenchHistory.objects.all()[:limit]]
    )


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def history_detail(request: HttpRequest, history_id: int) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    item = get_object_or_404(WorkbenchHistory, pk=history_id)
    if request.method == "DELETE":
        item.delete()
        return api_response(None)
    return api_response(serialize_history(item, detail=True))


@csrf_exempt
@require_http_methods(["POST"])
def rename_history(request: HttpRequest, history_id: int) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    item = get_object_or_404(WorkbenchHistory, pk=history_id)
    try:
        submission = RenameHistorySubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return _invalid(exc)
    item.name = submission.name
    item.save(update_fields=["name"])
    return api_response(serialize_history(item))
