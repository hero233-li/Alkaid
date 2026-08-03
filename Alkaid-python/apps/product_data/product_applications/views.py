import json

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.dispatch import enqueue_job
from apps.jobs.services import JobConflict, serialize_job
from apps.product_data.catalog import ProductCatalogError, load_product_ui_config
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.use_cases import submit_product_application
from apps.product_data.product_applications.validation import ProductConfigurationError


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
        created = submit_product_application(
            submission,
            idempotency_key=request.headers.get("X-Idempotency-Key"),
            trace_id=request.headers.get("X-Trace-ID"),
            timeout_seconds=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS,
        )
    except JobConflict as exc:
        return api_error(str(exc), status=409)
    except (
        ValidationError,
        ProductConfigurationError,
        ProductCatalogError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return api_error(f"产品申请参数无效：{exc}", status=400)

    if created.created:
        transaction.on_commit(lambda: enqueue_job(created.job))
    return api_response(
        serialize_job(created.job, include_payload=True),
        status=202 if created.created else 200,
    )
