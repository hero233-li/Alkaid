from typing import Any

from celery import current_app
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.core.responses import api_error, api_response
from apps.jobs.dispatch import enqueue_job
from apps.jobs.models import Job, JobApiCall
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
def job_detail(request: HttpRequest, job_id: int) -> JsonResponse:
    job = _get_job(job_id)
    if job is None:
        return api_error("Job 不存在", status=404)
    return api_response(serialize_job(job))


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
        return api_error(str(exc), status=409)
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
        return api_error(str(exc), status=409)
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


def _serialize_call(call: JobApiCall) -> dict[str, Any]:
    return {
        "id": call.id,
        "jobId": call.job_id,
        "taskId": call.celery_task_id,
        "attempt": call.attempt,
        "step": call.step,
        "method": call.method,
        "url": call.url,
        "requestHeaders": call.request_headers,
        "requestBody": call.request_body,
        "responseStatus": call.response_status,
        "responseHeaders": call.response_headers,
        "responseBody": call.response_body,
        "responseTruncated": call.response_truncated,
        "durationMs": call.duration_ms,
        "status": call.status,
        "errorType": call.error_type or None,
        "errorMessage": call.error_message or None,
        "startedAt": call.started_at.isoformat(),
        "finishedAt": call.finished_at.isoformat() if call.finished_at else None,
    }


@require_GET
def api_call_detail(request: HttpRequest, job_id: int, call_id: int) -> JsonResponse:
    try:
        call = JobApiCall.objects.get(id=call_id, job_id=job_id)
    except JobApiCall.DoesNotExist:
        return api_error("接口调用记录不存在", status=404)
    return api_response(_serialize_call(call))
