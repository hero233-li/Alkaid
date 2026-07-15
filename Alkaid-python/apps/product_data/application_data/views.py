from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.dispatch import enqueue_job
from apps.jobs.services import JobConflict, create_job, resolve_job_identifiers, serialize_job
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
        idempotency_key, trace_id = resolve_job_identifiers(
            request.headers.get("X-Idempotency-Key"), request.headers.get("X-Trace-ID")
        )
        created = create_job(
            kind="application_data.generate",
            name=f"申请数据生成-{submission.count}条",
            product="application-data",
            payload=submission.model_dump(mode="json", by_alias=True, exclude_none=True),
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            timeout_seconds=settings.APPLICATION_DATA_TIMEOUT_SECONDS,
            execution_config_version=1,
            execution_config_snapshot={"operation": "generate", "version": 1},
        )
    except ValidationError as exc:
        return api_error(f"申请数据生成参数无效：{exc}", status=400)
    except JobConflict as exc:
        return api_error(str(exc), status=409)
    except ValueError as exc:
        return api_error(str(exc), status=400)
    if created.created:
        transaction.on_commit(lambda: enqueue_job(created.job))
    return api_response(serialize_job(created.job), status=202 if created.created else 200)
