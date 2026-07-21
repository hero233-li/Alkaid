from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.http import submit_async_job
from apps.product_data.business_access.schemas import (
    BusinessAccessOperation,
    BusinessAccessPushSubmission,
    BusinessAccessRecordSubmission,
    BusinessAccessSearchSubmission,
)
from apps.product_data.business_access.services import get_business_access_config


@require_GET
def business_access_config(request: HttpRequest) -> JsonResponse:
    return api_response(get_business_access_config())


@csrf_exempt
@require_POST
def search_business_access(request: HttpRequest) -> JsonResponse:
    try:
        submission = BusinessAccessSearchSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"业务准入查询参数无效：{exc}", status=400)
    return _submit_job(
        request,
        operation=BusinessAccessOperation.SEARCH,
        payload=submission.model_dump(mode="json", by_alias=True, exclude_none=True),
        name="业务准入查询",
    )


@csrf_exempt
@require_POST
def invalidate_business_access(request: HttpRequest, record_id: int) -> JsonResponse:
    submission = BusinessAccessRecordSubmission(record_id=record_id)
    return _submit_job(
        request,
        operation=BusinessAccessOperation.INVALIDATE,
        payload=submission.model_dump(mode="json", by_alias=True),
        name=f"业务准入记录失效-{record_id}",
    )


@csrf_exempt
@require_POST
def query_business_access_notifications(request: HttpRequest, record_id: int) -> JsonResponse:
    submission = BusinessAccessRecordSubmission(record_id=record_id)
    return _submit_job(
        request,
        operation=BusinessAccessOperation.NOTIFICATIONS,
        payload=submission.model_dump(mode="json", by_alias=True),
        name=f"业务准入通知查询-{record_id}",
    )


@csrf_exempt
@require_POST
def push_business_access_notification(
    request: HttpRequest,
    record_id: int,
    notification_id: int,
    action: str,
) -> JsonResponse:
    if action not in {"push-new", "push-old"}:
        return api_error("通知推送操作无效", status=400)
    version_type = "latest" if action == "push-new" else "previous"
    submission = BusinessAccessPushSubmission(
        record_id=record_id,
        notification_id=notification_id,
        version_type=version_type,
    )
    return _submit_job(
        request,
        operation=BusinessAccessOperation.PUSH,
        payload=submission.model_dump(mode="json", by_alias=True),
        name=f"业务准入通知推送-{notification_id}-{version_type}",
    )


def _submit_job(
    request: HttpRequest,
    *,
    operation: BusinessAccessOperation,
    payload: dict[str, object],
    name: str,
) -> JsonResponse:
    return submit_async_job(
        request,
        kind="business_access",
        name=name,
        product="business-access",
        payload={"operation": operation.value, "data": payload},
        timeout_seconds=settings.BUSINESS_ACCESS_TIMEOUT_SECONDS,
        snapshot={"operation": operation.value, "version": 1},
    )
