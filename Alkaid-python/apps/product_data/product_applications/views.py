import json
import uuid

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.services import JobConflict, JobRepository, serialize_job
from apps.product_data.execution_config import (
    ExecutionConfigurationError,
    load_execution_catalog,
)
from apps.product_data.product_applications.config import (
    ProductConfigurationError,
    load_product_application_config,
)
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.services import validate_submission
from apps.product_data.product_applications.tasks import execute_product_application


@require_GET
def product_application_config(request: HttpRequest) -> JsonResponse:
    try:
        config = load_product_application_config()
    except ProductConfigurationError as exc:
        return api_error(str(exc), status=500)
    return api_response(config.model_dump(mode="json"))


@csrf_exempt
@require_POST
def create_product_application(request: HttpRequest) -> JsonResponse:
    try:
        submission = ProductApplicationSubmission.model_validate_json(request.body)
        execution_catalog = load_execution_catalog()
        execution_snapshot = execution_catalog.snapshot(
            submission.product,
            str(submission.payload.get("applicationMethod") or "") or None,
        )
        submission.payload["applicationMethod"] = execution_snapshot.method_code
        validate_submission(submission, execution_snapshot=execution_snapshot)
    except (
        ValidationError,
        ProductConfigurationError,
        ExecutionConfigurationError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return api_error(f"产品申请参数无效：{exc}", status=400)

    idempotency_key = request.headers.get("X-Idempotency-Key") or str(uuid.uuid4())
    trace_id = request.headers.get("X-Trace-ID") or uuid.uuid4().hex
    try:
        created = JobRepository.create(
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
        transaction.on_commit(lambda: execute_product_application.delay(created.job.id))
    return api_response(serialize_job(created.job), status=202 if created.created else 200)
