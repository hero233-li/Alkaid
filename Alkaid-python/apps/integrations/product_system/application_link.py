import json
from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from apps.integrations.application_link.api import CREATE_DYNAMIC_LINK, CREATE_SUN_CODE_LINK
from apps.integrations.application_link.models import (
    ApplicationLinks,
    GenerateApplicationLinkRequest,
)
from apps.integrations.auth import TokenManager
from apps.integrations.executor import EndpointExecutor
from apps.integrations.product_system.client import create_product_system_client
from apps.integrations.product_system.wire import build_five_field_form
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


def generate_application_link(
    job: Job, request: GenerateApplicationLinkRequest
) -> ApplicationLinks:
    endpoint = _endpoint_for(request.category)
    message = json.dumps(
        {
            "REQ_HEAD": {
                "traceno": job.trace_id,
                "starttime": job.created_at.isoformat(),
                "product": request.product,
            },
            "REQ_BODY": {"request": request.external_request()},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if settings.EXTERNAL_SYSTEM_MODE == "real" and not settings.APPLICATION_LINK_PROTOCOL_CONFIRMED:
        raise ImproperlyConfigured("申请链接真实协议尚未确认")
    client = create_product_system_client("application_link", request.env)
    try:
        response = EndpointExecutor(client, TokenManager({})).execute(
            endpoint,
            form_data=build_five_field_form(
                msg_id=job.trace_id,
                sign=_configured_sign(message),
                timestamp=datetime.now(timezone.utc).strftime(
                    settings.APPLICATION_LINK_TIMESTAMP_FORMAT
                ),
                message=message,
            ),
            trace_id=job.trace_id,
            observer=JobHttpCallObserver(job, step="application_link.generate_link"),
        )
        return response.data
    finally:
        client.close()


def _endpoint_for(category: str):
    if category == "动态链接":
        return CREATE_DYNAMIC_LINK
    if category == "太阳码":
        return CREATE_SUN_CODE_LINK
    raise ValueError(f"未知申请链接类别：{category}")


def _configured_sign(message: str) -> str:
    if settings.EXTERNAL_SYSTEM_MODE == "real":
        if not settings.APPLICATION_LINK_SIGNER:
            raise ImproperlyConfigured("APPLICATION_LINK_SIGNER 未配置")
        sign = import_string(settings.APPLICATION_LINK_SIGNER)(message)
        if not isinstance(sign, str) or not sign:
            raise ImproperlyConfigured("APPLICATION_LINK_SIGNER 必须返回非空字符串")
        return sign
    sign = settings.APPLICATION_LINK_FORM_SIGN
    if settings.APPLICATION_LINK_SIGN_REQUIRED and not sign:
        raise ImproperlyConfigured("APPLICATION_LINK_FORM_SIGN 未配置")
    return sign
