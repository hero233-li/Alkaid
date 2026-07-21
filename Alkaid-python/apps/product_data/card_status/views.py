from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.jobs.http import submit_async_job
from apps.product_data.card_status.schemas import (
    CardAction,
    CardActionSubmission,
    CardSearchSubmission,
    CardStatusOperation,
)
from apps.product_data.card_status.services import get_card_status_config


@require_GET
def card_status_config(request: HttpRequest) -> JsonResponse:
    del request
    return api_response(get_card_status_config())


@csrf_exempt
@require_POST
def search_cards(request: HttpRequest) -> JsonResponse:
    try:
        submission = CardSearchSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return api_error(f"卡状态查询参数无效：{exc}", status=400)
    return _submit_job(
        request,
        CardStatusOperation.SEARCH,
        submission.model_dump(mode="json", by_alias=True),
        "卡状态查询",
    )


@csrf_exempt
@require_POST
def apply_card_action(request: HttpRequest, card_no: str, action: str) -> JsonResponse:
    try:
        parsed_action = CardAction(action)
        values = CardActionSubmission.model_validate(
            {**_json_body(request), "action": parsed_action.value}
        )
    except (ValidationError, ValueError) as exc:
        return api_error(f"卡状态操作参数无效：{exc}", status=400)
    if values.card_no != card_no:
        return api_error("卡号与请求路径不一致", status=400)
    return _submit_job(
        request,
        CardStatusOperation.ACTION,
        values.model_dump(mode="json", by_alias=True, exclude_none=True),
        f"卡状态操作-{parsed_action.value}",
    )


def _submit_job(
    request: HttpRequest, operation: CardStatusOperation, payload: dict[str, object], name: str
) -> JsonResponse:
    return submit_async_job(
        request,
        kind="card_status",
        name=name,
        product="card-status",
        payload={"operation": operation.value, "data": payload},
        timeout_seconds=settings.CARD_STATUS_TIMEOUT_SECONDS,
        snapshot={"operation": operation.value, "version": 1},
    )


def _json_body(request: HttpRequest) -> dict[str, object]:
    import json

    value = json.loads(request.body.decode("utf-8") or "{}")
    if not isinstance(value, dict):
        raise ValueError("请求体必须为对象")
    return value
