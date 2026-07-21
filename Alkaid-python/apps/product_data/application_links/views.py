from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.http import submit_async_job
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
        return api_error(f"申请链接配置无效：{exc}", status=exc.status_code, code=exc.code)
    return api_response(config.model_dump(mode="json"))


@csrf_exempt
@require_POST
def generate_application_link(request: HttpRequest) -> JsonResponse:
    try:
        submission = normalize_submission(
            ApplicationLinkSubmission.model_validate_json(request.body)
        )
        execution_snapshot = resolve_execution_snapshot(submission)
    except (ValidationError, ApplicationLinkConfigurationError, ValueError) as exc:
        return api_error(f"申请链接参数无效：{exc}", status=400, code="invalid_submission")

    return submit_async_job(
        request,
        kind="application_link",
        name=f"申请链接生成-{submission.product}",
        product=submission.product,
        payload=submission_payload(submission),
        timeout_seconds=settings.APPLICATION_LINK_TIMEOUT_SECONDS,
        snapshot=execution_snapshot.model_dump(mode="json", exclude_none=True),
        snapshot_version=execution_snapshot.config_version,
    )
