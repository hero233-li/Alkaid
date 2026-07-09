import uuid

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.services import JobConflict, JobRepository, serialize_job
from apps.product_data.application_links.config import ApplicationLinkConfigurationError
from apps.product_data.application_links.schemas import (
    ApplicationLinkSubmission,
    submission_payload,
)
from apps.product_data.application_links.services import resolve_execution_snapshot
from apps.product_data.application_links.tasks import execute_application_link


@csrf_exempt
@require_POST
def generate_application_link(request: HttpRequest) -> JsonResponse:
    try:
        submission = ApplicationLinkSubmission.model_validate_json(request.body)
        execution_snapshot = resolve_execution_snapshot(submission)
    except (ValidationError, ApplicationLinkConfigurationError, ValueError) as exc:
        return api_error(f"申请链接参数无效：{exc}", status=400)

    idempotency_key = request.headers.get("X-Idempotency-Key") or str(uuid.uuid4())
    trace_id = request.headers.get("X-Trace-ID") or uuid.uuid4().hex
    try:
        created = JobRepository.create(
            kind="application_link_generation",
            name=f"申请链接生成-{submission.product}",
            product=submission.product,
            payload=submission_payload(submission),
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            timeout_seconds=settings.APPLICATION_LINK_TIMEOUT_SECONDS,
            execution_config_version=execution_snapshot.config_version,
            execution_config_snapshot=execution_snapshot.model_dump(mode="json"),
        )
    except JobConflict as exc:
        return api_error(str(exc), status=409)
    if created.created:
        transaction.on_commit(lambda: execute_application_link.delay(created.job.id))
    return api_response(serialize_job(created.job), status=202 if created.created else 200)
