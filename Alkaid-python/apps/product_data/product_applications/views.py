import json

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.dispatch import enqueue_job
from apps.jobs.services import JobConflict, create_job, resolve_job_identifiers, serialize_job
from apps.product_data.catalog import (
    ProductCatalogError,
    load_product_catalog,
    load_product_ui_config,
)
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.services import (
    ProductConfigurationError,
    validate_submission,
)


@require_GET
def product_application_config(request: HttpRequest) -> JsonResponse:
    try:
        config = load_product_ui_config()
    except ProductCatalogError as exc:
        return api_error(str(exc), status=500)
    return api_response(config.model_dump(mode="json"))


@csrf_exempt
@require_POST
def create_product_application(request: HttpRequest) -> JsonResponse:
    try:
        submission = ProductApplicationSubmission.model_validate_json(request.body)
        catalog = load_product_catalog()
        execution_snapshot = catalog.snapshot(
            submission.product,
            str(submission.payload.get("applicationMethod") or "") or None,
        )
        submission.payload["applicationMethod"] = execution_snapshot.method_code
        validate_submission(
            submission,
            execution_snapshot=execution_snapshot,
            catalog=catalog,
        )
        idempotency_key, trace_id = resolve_job_identifiers(
            request.headers.get("X-Idempotency-Key"),
            request.headers.get("X-Trace-ID"),
        )
    except (
        ValidationError,
        ProductConfigurationError,
        ProductCatalogError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return api_error(f"产品申请参数无效：{exc}", status=400)

    try:
        created = create_job(
            kind="product_application",
            name=submission.name,
            product=submission.product,
            payload=submission.payload,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            timeout_seconds=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS,
            execution_config_version=execution_snapshot.catalog_version,
            execution_config_snapshot=execution_snapshot.model_dump(mode="json"),
        )
    except JobConflict as exc:
        return api_error(str(exc), status=409)
    if created.created:
        transaction.on_commit(lambda: enqueue_job(created.job))
    return api_response(
        serialize_job(created.job, include_payload=True),
        status=202 if created.created else 200,
    )
