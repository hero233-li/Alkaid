from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.workflow.Apifox.models import WorkbenchHistory, WorkbenchPackage, WorkbenchPackageRequest
from apps.workflow.Apifox.schemas import RenameHistorySubmission, WorkbenchRequest
from apps.workflow.Apifox.services import (
    serialize_history,
    serialize_package,
    serialize_package_request_detail,
)
from apps.workflow.Apifox.use_cases import execute_workbench_request, import_saz_package


def _invalid(exc: Exception) -> JsonResponse:
    return api_error(f"接口工作台参数无效：{exc}", status=400, code="invalid_submission")


def _disabled() -> JsonResponse | None:
    if settings.WORKBENCH_ENABLED:
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
    try:
        return api_response(execute_workbench_request(submission).as_api_result())
    except ValueError as exc:
        return _invalid(exc)


@csrf_exempt
@require_http_methods(["POST"])
def execute_multipart(request: HttpRequest) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    try:
        submission = WorkbenchRequest.model_validate_json(request.POST.get("payload", ""))
    except ValidationError as exc:
        return _invalid(exc)
    try:
        outcome = execute_workbench_request(submission, request.FILES)
        return api_response(outcome.as_api_result())
    except ValueError as exc:
        return _invalid(exc)


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


@csrf_exempt
@require_http_methods(["GET"])
def packages(request: HttpRequest) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    items = WorkbenchPackage.objects.prefetch_related("requests").all()
    return api_response([serialize_package(item) for item in items])


@csrf_exempt
@require_http_methods(["POST"])
def import_saz(request: HttpRequest) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    upload = request.FILES.get("file")
    if upload is None:
        return api_error("请选择要导入的 SAZ 文件", status=400, code="invalid_submission")
    try:
        package = import_saz_package(upload)
    except ValueError as exc:
        return _invalid(exc)
    return api_response(serialize_package(package), status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
def package_detail(request: HttpRequest, package_id: int) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    package = get_object_or_404(WorkbenchPackage, pk=package_id)
    package.delete()
    return api_response(None)


@require_http_methods(["GET"])
def package_request_detail(
    request: HttpRequest,
    package_id: int,
    request_id: int,
) -> JsonResponse:
    if disabled := _disabled():
        return disabled
    item = get_object_or_404(
        WorkbenchPackageRequest,
        pk=request_id,
        package_id=package_id,
    )
    return api_response(serialize_package_request_detail(item))
