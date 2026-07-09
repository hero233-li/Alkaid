import json
from urllib.parse import parse_qs

import httpx
from pydantic import BaseModel

from apps.integrations.example_system.adapter import ExampleSystemAdapter
from apps.integrations.example_system.models import ExampleLookupRequest
from apps.integrations.http import HttpClient, HttpClientConfig


class FormResponse(BaseModel):
    ok: bool


def test_adapter_converts_nested_wire_response_to_typed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Trace-ID"] == "workflow-1"
        assert request.url.params["value"] == "raw"
        return httpx.Response(
            200,
            json={"data": {"reference": "ref-1", "display_value": "Typed value"}},
        )

    client = HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = ExampleSystemAdapter(client).lookup(
            ExampleLookupRequest(value="raw"), workflow_id="workflow-1"
        )
    finally:
        client.close()

    assert result.reference == "ref-1"
    assert result.display_value == "Typed value"


def test_http_client_retries_retryable_status():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(
            200,
            json={"data": {"reference": "ref-2", "display_value": "ok"}},
        )

    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=1),
        transport=httpx.MockTransport(handler),
    ) as client:
        result = ExampleSystemAdapter(client).lookup(
            ExampleLookupRequest(value="raw"), workflow_id="workflow-2"
        )

    assert attempts == 2
    assert result.reference == "ref-2"


def test_http_client_serializes_multi_field_urlencoded_form():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Content-Type"].startswith(
            "application/x-www-form-urlencoded"
        )
        form = parse_qs(request.content.decode(), keep_blank_values=True)
        assert json.loads(form["req_message"][0]) == {
            "req_head": {"traceno": "trace-1"},
            "req_body": {"request": {"name": "张三"}},
        }
        assert json.loads(form["bizcond"][0]) == {"type": "01"}
        assert form["starttime"] == ["20260704150000"]
        assert form["enabled"] == ["false"]
        return httpx.Response(200, json={"ok": True})

    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=0),
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.request(
            "POST",
            "/form",
            response_model=FormResponse,
            form_data={
                "req_message": {
                    "req_head": {"traceno": "trace-1"},
                    "req_body": {"request": {"name": "张三"}},
                },
                "bizcond": {"type": "01"},
                "starttime": "20260704150000",
                "enabled": False,
                "omitted": None,
            },
            workflow_id="trace-1",
        )

    assert result.ok is True
