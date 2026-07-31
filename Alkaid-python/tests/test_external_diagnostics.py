import json

import httpx
import pytest
from pydantic import BaseModel, Field

from apps.integrations.http import (
    ExternalServiceError,
    HttpClient,
    HttpClientConfig,
)
from apps.jobs.http import sanitize, sanitize_url


class ExpectedEnvelope(BaseModel):
    rsp_body: dict = Field(alias="RSP_BODY")


def test_json_form_messages_keep_structure_but_mask_secrets() -> None:
    raw = json.dumps(
        {
            "REQ_BODY": {
                "myPrivateKey": "PRIVATE-KEY-VALUE",
                "request": {
                    "personName": "测试用户",
                    "phone": "13800138000",
                },
            }
        },
        ensure_ascii=False,
    )

    result = sanitize(
        {
            "REQ_MESSAGE": raw,
            "biz_content": raw,
        }
    )

    assert result["REQ_MESSAGE"]["REQ_BODY"]["request"]["personName"] == "测试用户"
    assert result["REQ_MESSAGE"]["REQ_BODY"]["request"]["phone"] != "13800138000"
    assert result["REQ_MESSAGE"]["REQ_BODY"]["myPrivateKey"] != "PRIVATE-KEY-VALUE"


def test_url_keeps_path_and_masks_auth_value() -> None:
    value = sanitize_url(
        "http://example.test/index.html?auth=SECRET&mode=1#/page"
    )

    assert "example.test/index.html" in value
    assert "auth=SECRET" not in value
    assert "mode=1" in value


def test_business_failure_message_is_explicit() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "biz_state": "F",
                "rsp_code": "TOKEN_ERROR",
                "rsp_msg": "获取客户端TokenId失败",
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
            Exception,
            match="获取客户端TokenId失败",
        ):
            client.request(
                "POST",
                "/agreement",
                response_model=ExpectedEnvelope,
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
