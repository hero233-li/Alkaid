import json

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.http import submit_async_job
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
        return api_error(str(exc), status=exc.status_code, code=exc.code)
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
    except ProductCatalogError as exc:
        return api_error(str(exc), status=exc.status_code, code=exc.code)
    except (ValidationError, ProductConfigurationError, ValueError, json.JSONDecodeError) as exc:
        return api_error(f"产品申请参数无效：{exc}", status=400, code="invalid_submission")

    return submit_async_job(
        request,
        kind="product_application",
        name=submission.name,
        product=submission.product,
        payload=submission.payload,
        timeout_seconds=settings.PRODUCT_APPLICATION_TIMEOUT_SECONDS,
        snapshot=execution_snapshot.model_dump(mode="json"),
        snapshot_version=execution_snapshot.catalog_version,
    )
