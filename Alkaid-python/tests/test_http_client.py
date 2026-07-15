import httpx
import pytest
from pydantic import BaseModel

from apps.integrations.auth import TokenManager
from apps.integrations.contracts import EndpointSpec, RetryMode
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import ExternalServiceError, HttpClient, HttpClientConfig


class Response(BaseModel):
    code: str


def test_http_client_serializes_form_objects_and_propagates_trace_id() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        captured["trace"] = request.headers["X-Trace-ID"]
        return httpx.Response(200, json={"code": "0000"})

    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=0),
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.request(
            "POST",
            "/form",
            response_model=Response,
            form_data={"payload": {"a": 1}, "req_message": {"REQ_BODY": {}}},
            trace_id="trace-123",
        )

    assert response.code == "0000"
    assert captured["trace"] == "trace-123"
    assert "req_message=%7B%22REQ_BODY%22%3A%7B%7D%7D" in str(captured["body"])


def test_safe_endpoint_retries_retry_after_but_never_endpoint_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("apps.integrations.http.time.sleep", sleeps.append)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "10"}, json={"code": "busy"})
        return httpx.Response(200, json={"code": "0000"})

    safe = EndpointSpec(
        operation_id="safe",
        method="GET",
        path="/safe",
        response_model=Response,
        retry_mode=RetryMode.SAFE,
    )
    with HttpClient(
        HttpClientConfig(
            base_url="https://example.test",
            max_retries=1,
            retry_max_backoff_seconds=0.5,
        ),
        transport=httpx.MockTransport(handler),
    ) as client:
        result = EndpointExecutor(client, TokenManager({})).execute(safe, trace_id="trace")

    assert result.code == "0000"
    assert calls == 2
    assert sleeps == [0.5]

    calls = 0
    never = EndpointSpec(
        operation_id="never",
        method="POST",
        path="/never",
        response_model=Response,
    )
    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=1),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ExternalServiceError):
            EndpointExecutor(client, TokenManager({})).execute(never, trace_id="trace")
    assert calls == 1
