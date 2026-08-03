import httpx
import pytest
from pydantic import BaseModel

from apps.integrations.contracts import RetryMode
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


def test_never_does_not_retry_5xx() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"code": "busy"})

    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=2),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ExternalServiceError):
            client.request("POST", "/items", response_model=Response)
    assert calls == 1


def test_connect_only_retries_connect_error_but_not_read_error(monkeypatch) -> None:
    monkeypatch.setattr("apps.integrations.http.time.sleep", lambda _: None)
    calls = 0

    def connect_then_success(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connect", request=request)
        return httpx.Response(200, json={"code": "0000"})

    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=1),
        transport=httpx.MockTransport(connect_then_success),
    ) as client:
        assert (
            client.request(
                "GET", "/items", response_model=Response, retry_mode=RetryMode.CONNECT_ONLY
            ).code
            == "0000"
        )
    assert calls == 2

    calls = 0

    def read_failure(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadError("read", request=request)

    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=2),
        transport=httpx.MockTransport(read_failure),
    ) as client:
        with pytest.raises(ExternalServiceError):
            client.request(
                "GET", "/items", response_model=Response, retry_mode=RetryMode.CONNECT_ONLY
            )
    assert calls == 1


def test_idempotent_retries_5xx_and_jitter_is_applied(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("apps.integrations.http.time.sleep", sleeps.append)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            503 if calls == 1 else 200,
            json={"code": "busy" if calls == 1 else "0000"},
        )

    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=1, retry_backoff_seconds=1),
        transport=httpx.MockTransport(handler),
        random_uniform=lambda low, high: 1.2,
    ) as client:
        result = client.request(
            "GET", "/items", response_model=Response, retry_mode=RetryMode.IDEMPOTENT
        )
    assert result.code == "0000"
    assert calls == 2
    assert sleeps == [1.2]


def test_http_400_and_schema_error_are_not_retried() -> None:
    for payload, status in [({"code": "bad"}, 400), ({"unexpected": True}, 200)]:
        calls = 0

        def handler(
            request: httpx.Request,
            response_status: int = status,
            response_payload: dict = payload,
        ) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(response_status, json=response_payload)

        with HttpClient(
            HttpClientConfig(base_url="https://example.test", max_retries=2),
            transport=httpx.MockTransport(handler),
        ) as client:
            with pytest.raises(ExternalServiceError):
                client.request(
                    "GET", "/items", response_model=Response, retry_mode=RetryMode.IDEMPOTENT
                )
        assert calls == 1


def test_response_body_limit_is_enforced() -> None:
    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_response_bytes=4),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b'{"code":"0000"}')
        ),
    ) as client:
        with pytest.raises(ExternalServiceError, match="响应体超过上限"):
            client.request("GET", "/items", response_model=Response)
