from celery import current_app
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, TextField
from django.db.models.functions import Cast
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.core.responses import api_error, api_response
from apps.jobs.dispatch import enqueue_job
from apps.jobs.models import Job, JobApiCall, JobLog
from apps.jobs.serializers import serialize_api_call, serialize_job_summary
from apps.jobs.services import (
    InvalidJobTransition,
    add_job_log,
    request_job_cancel,
    request_job_retry,
    serialize_job,
    serialize_log,
)


def _get_job(job_id: int) -> Job | None:
    try:
        return Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return None


@require_GET
def job_list(request: HttpRequest) -> JsonResponse:
    queryset = Job.objects.annotate(api_call_count=Count("api_calls", distinct=True))
    status = request.GET.get("status", "").strip()
    query = request.GET.get("query", "").strip()
    if status:
        queryset = queryset.filter(status=status)
    if query:
        matching_logs = (
            JobLog.objects.filter(job_id=OuterRef("pk"))
            .annotate(search_metadata=Cast("metadata", output_field=TextField()))
            .filter(
                Q(message__icontains=query)
                | Q(step__icontains=query)
                | Q(search_metadata__icontains=query)
            )
        )
        matching_calls = (
            JobApiCall.objects.filter(job_id=OuterRef("pk"))
            .annotate(
                search_request=Cast("request_body", output_field=TextField()),
                search_response=Cast("response_body", output_field=TextField()),
            )
            .filter(
                Q(step__icontains=query)
                | Q(method__icontains=query)
                | Q(url__icontains=query)
                | Q(error_message__icontains=query)
                | Q(search_request__icontains=query)
                | Q(search_response__icontains=query)
            )
        )
        queryset = queryset.annotate(
            has_matching_log=Exists(matching_logs),
            has_matching_call=Exists(matching_calls),
        )
        filters = (
            Q(name__icontains=query)
            | Q(product__icontains=query)
            | Q(stage__icontains=query)
            | Q(trace_id__icontains=query)
            | Q(idempotency_key__icontains=query)
            | Q(celery_task_id__icontains=query)
            | Q(has_matching_log=True)
            | Q(has_matching_call=True)
        )
        if query.isdigit():
            filters |= Q(id=int(query))
        queryset = queryset.filter(filters)
    try:
        limit = min(100, max(1, int(request.GET.get("limit", "5"))))
    except ValueError:
        return api_error("limit 必须是整数", status=400)
    queryset = queryset.order_by("-created_at", "-id")
    return api_response([serialize_job_summary(job) for job in queryset[:limit]])


@require_GET
def job_detail(request: HttpRequest, job_id: int) -> JsonResponse:
    job = _get_job(job_id)
    if job is None:
        return api_error("Job 不存在", status=404)
    include_payload = (
        request.GET.get("includePayload", "").lower() == "true"
        and job.kind == "product_application"
    )
    return api_response(serialize_job(job, include_payload=include_payload))


@require_GET
def job_payload_detail(request: HttpRequest, job_id: int) -> JsonResponse:
    if not request.user.is_authenticated or not request.user.is_staff:
        return api_error("无权查看 Job 原始参数", status=403)
    job = _get_job(job_id)
    if job is None:
        return api_error("Job 不存在", status=404)
    return api_response({"id": job.id, "payload": job.payload})


@csrf_exempt
@require_POST
def retry_job(request: HttpRequest, job_id: int) -> JsonResponse:
    if _get_job(job_id) is None:
        return api_error("Job 不存在", status=404)
    try:
        job = request_job_retry(job_id)
    except InvalidJobTransition as exc:
        return api_error(str(exc), status=exc.status_code, code=exc.code)
    transaction.on_commit(lambda: enqueue_job(job))
    return api_response(serialize_job(job))


@csrf_exempt
@require_POST
def cancel_job(request: HttpRequest, job_id: int) -> JsonResponse:
    job = _get_job(job_id)
    if job is None:
        return api_error("Job 不存在", status=404)
    try:
        job = request_job_cancel(job_id)
    except InvalidJobTransition as exc:
        return api_error(str(exc), status=exc.status_code, code=exc.code)
    if job.celery_task_id:
        try:
            current_app.control.revoke(job.celery_task_id, terminate=False)
        except Exception as exc:
            add_job_log(
                job,
                "WARN",
                f"向 Celery 发送撤销通知失败，将由任务状态阻止后续执行：{exc}",
                step="cancel_requested",
                celery_task_id=job.celery_task_id,
            )
    return api_response(serialize_job(job))


@require_GET
def job_logs(request: HttpRequest, job_id: int) -> JsonResponse:
    job = _get_job(job_id)
    if job is None:
        return api_error("Job 不存在", status=404)
    try:
        after_id = max(0, int(request.GET.get("afterId", "0")))
    except ValueError:
        return api_error("afterId 必须是整数", status=400)
    logs = job.logs.filter(id__gt=after_id).order_by("id")[:500]
    return api_response([serialize_log(log) for log in logs])


@require_GET
def api_call_detail(request: HttpRequest, job_id: int, call_id: int) -> JsonResponse:
    try:
        call = JobApiCall.objects.get(id=call_id, job_id=job_id)
    except JobApiCall.DoesNotExist:
        return api_error("接口调用记录不存在", status=404)
    return api_response(serialize_api_call(call))
