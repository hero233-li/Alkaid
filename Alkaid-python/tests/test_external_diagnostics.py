import json

import httpx
import pytest
from django.test import override_settings
from pydantic import BaseModel, Field

from apps.utils.http.client import (
    ExternalServiceError,
    HttpClient,
    HttpClientConfig,
)
from apps.workflow.Jobs.http import limit_body
from apps.workflow.Jobs.integration_observer import JobIntegrationObserver
from apps.workflow.Jobs.models import JobApiCall
from apps.workflow.Jobs.services import create_job
from apps.workflow.product_applications.cjdk.client import validate_cjdk_business_response


class ExpectedEnvelope(BaseModel):
    rsp_body: dict = Field(alias="RSP_BODY")


def test_http_body_keeps_secrets_and_base64_verbatim_within_limit() -> None:
    raw = json.dumps(
        {
            "REQ_BODY": {
                "myPrivateKey": "PRIVATE-KEY-VALUE",
                "request": {
                    "personName": "测试用户",
                    "phone": "13800138000",
                    "downFile": "JVBERi0xLjQK",
                },
            }
        },
        ensure_ascii=False,
    )

    result, truncated = limit_body(
        {
            "REQ_MESSAGE": raw,
            "biz_content": raw,
        }
    )

    assert truncated is False
    assert result["REQ_MESSAGE"] == raw
    assert "13800138000" in result["REQ_MESSAGE"]
    assert "PRIVATE-KEY-VALUE" in result["REQ_MESSAGE"]
    assert "JVBERi0xLjQK" in result["REQ_MESSAGE"]


@override_settings(JOB_MAX_HTTP_BODY_BYTES=40)
def test_http_body_uses_one_raw_prefix_truncation_rule() -> None:
    value = {"downFile": "A" * 100, "token": "SECRET"}
    stored, truncated = limit_body(value)

    assert truncated is True
    assert stored["truncated"] is True
    assert stored["originalBytes"] == len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    assert stored["preview"].startswith('{"downFile": "')


@pytest.mark.django_db
def test_job_api_call_preserves_raw_url_headers_bodies_and_exception() -> None:
    job = create_job(
        kind="diagnostic",
        name="原文审计",
        product="test",
        payload={},
        trace_id="raw-diagnostic",
        idempotency_key="raw-diagnostic",
        timeout_seconds=60,
    ).job
    observer = JobIntegrationObserver(job)
    url = "https://service.test/path?token=TOKEN-RAW&phone=13800138000"
    request_headers = {"Authorization": "Bearer SECRET", "Cookie": "SID=COOKIE-RAW"}
    request_body = {
        "privateKey": "PRIVATE-KEY-RAW",
        "certificateNo": "330101199001011234",
        "downFile": "JVBERi0xLjQK",
    }
    handle = observer.request_started(
        step="raw",
        method="POST",
        url=url,
        headers=request_headers,
        body=request_body,
    )
    error = RuntimeError("验证码 123456；TOKEN-RAW；完整异常原文")
    observer.request_finished(
        handle,
        status_code=500,
        headers={"Set-Cookie": "SESSION=RESPONSE-COOKIE"},
        body={"token": "RESPONSE-TOKEN", "downFile": "JVBERi0xLjQK"},
        duration_ms=12,
        error=error,
    )

    call = JobApiCall.objects.get(pk=handle)
    assert call.url == url
    assert call.request_headers == request_headers
    assert call.request_body == request_body
    assert call.response_headers == {"Set-Cookie": "SESSION=RESPONSE-COOKIE"}
    assert call.response_body == {"token": "RESPONSE-TOKEN", "downFile": "JVBERi0xLjQK"}
    assert call.error_message == str(error)


def test_cjdk_business_failure_message_is_explicit() -> None:
    with pytest.raises(Exception, match="获取客户端TokenId失败"):
        validate_cjdk_business_response(
            {
                "biz_state": "F",
                "rsp_code": "TOKEN_ERROR",
                "rsp_msg": "获取客户端TokenId失败",
            }
        )


def test_invalid_schema_message_lists_actual_fields() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "unexpected": True,
            },
        )
    )

    with HttpClient(
        HttpClientConfig(
            base_url="http://example.test",
            max_retries=0,
        ),
        transport=transport,
    ) as client:
        with pytest.raises(
            ExternalServiceError,
            match="实际顶层字段=unexpected",
        ):
            client.request(
                "POST",
                "/agreement",
                response_model=ExpectedEnvelope,
            )
