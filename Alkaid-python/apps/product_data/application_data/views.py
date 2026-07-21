from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.http import submit_async_job
from apps.product_data.application_data.schemas import ApplicationDataSubmission
from apps.product_data.application_data.services import get_application_data_config


@require_GET
def application_data_config(request: HttpRequest) -> JsonResponse:
    del request
    return api_response(get_application_data_config())


@csrf_exempt
@require_POST
def generate_application_data(request: HttpRequest) -> JsonResponse:
    try:
        submission = ApplicationDataSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"申请数据生成参数无效：{exc}", status=400)
    return submit_async_job(
        request,
        kind="application_data",
        name=f"申请数据生成-{submission.count}条",
        product="application-data",
        payload={
            "operation": "generate",
            "data": submission.model_dump(mode="json", by_alias=True, exclude_none=True),
        },
        timeout_seconds=settings.APPLICATION_DATA_TIMEOUT_SECONDS,
        snapshot={"operation": "generate", "version": 1},
    )
