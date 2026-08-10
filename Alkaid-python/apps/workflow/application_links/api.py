from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.utils.product_Conf.catalog import ProductCatalogError
from apps.workflow.Jobs.dispatch import enqueue_job
from apps.workflow.Jobs.services import (
    JobConflict,
    create_job,
    resolve_job_identifiers,
    serialize_job,
)
from apps.workflow.Jobs.use_cases import enqueue_created_job

from .schemas import ApplicationLinkSubmission
from .service import (
    ApplicationLinkConfigurationError,
    get_application_link_config,
    resolve_execution_snapshot,
    submission_payload,
)


@require_GET
def application_link_config(request: HttpRequest) -> JsonResponse:
    del request
    try:
        config = get_application_link_config()
    except ProductCatalogError as exc:
        return api_error(f"申请链接配置无效：{exc}", status=500)
    return api_response(config)


@csrf_exempt
@require_POST
def create_application_link(request: HttpRequest) -> JsonResponse:
    try:
        submission, snapshot = resolve_execution_snapshot(
            ApplicationLinkSubmission.model_validate_json(request.body)
        )
        idempotency_key, trace_id = resolve_job_identifiers(
            request.headers.get("X-Idempotency-Key"),
            request.headers.get("X-Trace-ID"),
        )
        created = create_job(
            kind="application_link_generation",
            name=f"申请链接生成-{submission.product}",
            product=submission.product,
            payload=submission_payload(submission),
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            timeout_seconds=settings.APPLICATION_LINK_TIMEOUT_SECONDS,
            execution_config_version=snapshot.catalog_version,
            execution_config_snapshot=snapshot.model_dump(mode="json"),
        )
    except JobConflict as exc:
        return api_error(str(exc), status=409)
    except (
        ValidationError,
        ProductCatalogError,
        ApplicationLinkConfigurationError,
        ValueError,
    ) as exc:
        return api_error(f"申请链接参数无效：{exc}", status=400)
    enqueue_created_job(created, enqueue=enqueue_job)
    return api_response(serialize_job(created.job), status=202 if created.created else 200)
