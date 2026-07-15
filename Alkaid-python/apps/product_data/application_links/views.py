from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.dispatch import enqueue_job
from apps.jobs.services import JobConflict, create_job, resolve_job_identifiers, serialize_job
from apps.product_data.application_links.schemas import (
    ApplicationLinkSubmission,
    submission_payload,
)
from apps.product_data.application_links.services import (
    ApplicationLinkConfigurationError,
    get_application_link_config,
    normalize_submission,
    resolve_execution_snapshot,
)
from apps.product_data.catalog import ProductCatalogError


@require_GET
def application_link_config(request: HttpRequest) -> JsonResponse:
    del request
    try:
        config = get_application_link_config()
    except ProductCatalogError as exc:
        return api_error(f"申请链接配置无效：{exc}", status=500)
    return api_response(config.model_dump(mode="json"))


@csrf_exempt
@require_POST
def generate_application_link(request: HttpRequest) -> JsonResponse:
    try:
        submission = normalize_submission(
            ApplicationLinkSubmission.model_validate_json(request.body)
        )
        execution_snapshot = resolve_execution_snapshot(submission)
        idempotency_key, trace_id = resolve_job_identifiers(
            request.headers.get("X-Idempotency-Key"),
            request.headers.get("X-Trace-ID"),
        )
    except (ValidationError, ApplicationLinkConfigurationError, ValueError) as exc:
        return api_error(f"申请链接参数无效：{exc}", status=400)

    try:
        created = create_job(
            kind="application_link_generation",
            name=f"申请链接生成-{submission.product}",
            product=submission.product,
            payload=submission_payload(submission),
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            timeout_seconds=settings.APPLICATION_LINK_TIMEOUT_SECONDS,
            execution_config_version=execution_snapshot.config_version,
            execution_config_snapshot=execution_snapshot.model_dump(mode="json", exclude_none=True),
        )
    except JobConflict as exc:
        return api_error(str(exc), status=409)
    if created.created:
        transaction.on_commit(lambda: enqueue_job(created.job))
    return api_response(serialize_job(created.job), status=202 if created.created else 200)
