from celery import current_app
from django.db.models import Count, Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.responses import api_error, api_response
from apps.workflow.Jobs.dispatch import enqueue_job
from apps.workflow.Jobs.models import Job, JobApiCall, JobStatus
from apps.workflow.Jobs.services import (
    InvalidJobTransition,
    serialize_api_call,
    serialize_job,
    serialize_log,
)
from apps.workflow.Jobs.use_cases import cancel_job as cancel_job_use_case
from apps.workflow.Jobs.use_cases import delete_all_jobs as delete_all_jobs_use_case
from apps.workflow.Jobs.use_cases import retry_job as retry_job_use_case


def _get_job(job_id: int) -> Job | None:
    try:
        return Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return None


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def job_list(request: HttpRequest) -> JsonResponse:
    if request.method == "DELETE":
        result = delete_all_jobs_use_case()
        return api_response(result, message="已结束任务记录已全部清除")
    status = request.GET.get("status", "").strip()
    valid_statuses = {value for value, _label in JobStatus.choices}
    if status and status not in valid_statuses:
        return api_error("status 参数无效", status=400)
    try:
        page = int(request.GET.get("page", "1"))
        page_size = int(request.GET.get("pageSize", request.GET.get("limit", "5")))
    except ValueError:
        return api_error("page 和 pageSize 必须是整数", status=400)
    if page < 1:
        return api_error("page 必须大于等于 1", status=400)
    if page_size < 1 or page_size > 100:
        return api_error("pageSize 必须在 1 到 100 之间", status=400)

    query = request.GET.get("query", "").strip()
    jobs = Job.objects.all()
    if status:
        jobs = jobs.filter(status=status)
    if query:
        search = (
            Q(name__icontains=query)
            | Q(product__icontains=query)
            | Q(kind__icontains=query)
            | Q(trace_id__icontains=query)
            | Q(idempotency_key__icontains=query)
            | Q(error_message__icontains=query)
            | Q(logs__message__icontains=query)
            | Q(logs__step__icontains=query)
            | Q(api_calls__step__icontains=query)
            | Q(api_calls__method__icontains=query)
            | Q(api_calls__url__icontains=query)
            | Q(api_calls__error_message__icontains=query)
        )
        if query.isdigit():
            search |= Q(id=int(query))
        jobs = jobs.filter(search).distinct()
    total = jobs.count()
    offset = (page - 1) * page_size
    jobs = jobs.annotate(api_call_count=Count("api_calls", distinct=True)).order_by(
        "-created_at", "-id"
    )[offset : offset + page_size]
    items = [serialize_job(job, include_logs=False, include_api_calls=False) for job in jobs]
    return api_response(
        {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": (total + page_size - 1) // page_size,
        }
    )


@require_GET
def job_detail(request: HttpRequest, job_id: int) -> JsonResponse:
    try:
        job = Job.objects.prefetch_related("logs", "api_calls").get(id=job_id)
    except Job.DoesNotExist:
        return api_error("Job 不存在", status=404)
    include_payload = request.GET.get("includePayload", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    log_view = request.GET.get("logView", "all").strip().lower()
    if log_view not in {"all", "business"}:
        return api_error("logView 参数无效", status=400)
    return api_response(
        serialize_job(
            job,
            include_api_calls=log_view == "all",
            include_payload=include_payload,
            log_view=log_view,
        )
    )


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
    try:
        job = retry_job_use_case(job_id, enqueue=enqueue_job)
    except Job.DoesNotExist:
        return api_error("Job 不存在", status=404)
    except InvalidJobTransition as exc:
        return api_error(str(exc), status=409)
    return api_response(serialize_job(job))


@csrf_exempt
@require_POST
def cancel_job(request: HttpRequest, job_id: int) -> JsonResponse:
    try:
        job = cancel_job_use_case(
            job_id,
            revoke=lambda task_id: current_app.control.revoke(task_id, terminate=False),
        )
    except Job.DoesNotExist:
        return api_error("Job 不存在", status=404)
    except InvalidJobTransition as exc:
        return api_error(str(exc), status=409)
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
    log_view = request.GET.get("view", "all").strip().lower()
    if log_view not in {"all", "business"}:
        return api_error("view 参数无效", status=400)
    logs = job.logs.filter(id__gt=after_id)
    if log_view == "business":
        logs = logs.filter(metadata__audience="application_detail")
    logs = logs.order_by("id")[:500]
    return api_response([serialize_log(log) for log in logs])


@require_GET
def api_call_detail(request: HttpRequest, job_id: int, call_id: int) -> JsonResponse:
    try:
        call = JobApiCall.objects.get(id=call_id, job_id=job_id)
    except JobApiCall.DoesNotExist:
        return api_error("接口调用记录不存在", status=404)
    return api_response(serialize_api_call(call))
