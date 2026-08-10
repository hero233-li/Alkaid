import httpx
import pytest
from pydantic import BaseModel

from apps.utils.http.client import ExternalServiceError, HttpClient, HttpClientConfig, HttpFile
from apps.utils.http.contracts import RetryMode


class Response(BaseModel):
    code: str


class XmlItem(BaseModel):
    id: int
    name: str


class XmlItems(BaseModel):
    item: list[XmlItem]


class XmlResponse(BaseModel):
    code: str
    items: XmlItems


class RecordingIntegrationObserver:
    def __init__(self) -> None:
        self.started: dict[str, object] | None = None
        self.finished: dict[str, object] | None = None

    def request_started(self, **event: object) -> object:
        self.started = event
        return "request-handle"

    def request_finished(self, handle: object, **event: object) -> None:
        self.finished = {"handle": handle, **event}

    def diagnostic(self, **event: object) -> None:
        pass


def test_http_client_uses_integration_observer_directly() -> None:
    observer = RecordingIntegrationObserver()
    with HttpClient(
        HttpClientConfig(base_url="https://example.test"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"code": "0000"})),
    ) as client:
        response = client.request(
            "POST",
            "/items",
            response_model=Response,
            observer=observer,
            step="product.submit",
        )

    assert response.code == "0000"
    assert observer.started is not None
    assert observer.started["step"] == "product.submit"
    assert observer.started["method"] == "POST"
    assert observer.started["url"] == "https://example.test/items"
    assert observer.finished is not None
    assert observer.finished["handle"] == "request-handle"
    assert observer.finished["status_code"] == 200
    assert observer.finished["error"] is None


def test_http_client_requires_step_when_observer_is_provided() -> None:
    with HttpClient(HttpClientConfig(base_url="https://example.test")) as client:
        with pytest.raises(ValueError, match="必须提供 step"):
            client.request(
                "GET",
                "/items",
                response_model=Response,
                observer=RecordingIntegrationObserver(),
            )


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
    monkeypatch.setattr("apps.utils.http.client.time.sleep", lambda _: None)
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
    monkeypatch.setattr("apps.utils.http.client.time.sleep", sleeps.append)
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


def test_http_client_uploads_multipart_file_with_form_fields() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["content_type"] = request.headers["Content-Type"]
        captured["body"] = request.content
        return httpx.Response(200, json={"code": "0000"})

    with HttpClient(
        HttpClientConfig(base_url="https://example.test"),
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.request(
            "POST",
            "/upload",
            response_model=Response,
            form_data={"category": "contract"},
            files={
                "document": HttpFile(
                    filename="contract.xml",
                    content=b"<contract>content</contract>",
                    content_type="application/xml",
                )
            },
        )

    assert response.code == "0000"
    assert str(captured["content_type"]).startswith("multipart/form-data; boundary=")
    body = bytes(captured["body"])
    assert b'name="category"' in body
    assert b"contract" in body
    assert b'name="document"; filename="contract.xml"' in body
    assert b"Content-Type: application/xml" in body
    assert b"<contract>content</contract>" in body


def test_http_client_sends_and_parses_xml() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["content_type"] = request.headers["Content-Type"]
        captured["body"] = request.content
        return httpx.Response(
            200,
            content=(
                b"<response><code>0000</code><items>"
                b"<item><id>1</id><name>first</name></item>"
                b"<item><id>2</id><name>second</name></item>"
                b"</items></response>"
            ),
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )

    with HttpClient(
        HttpClientConfig(base_url="https://example.test"),
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.request(
            "POST",
            "/xml",
            response_model=XmlResponse,
            raw_body="<query><id>42</id></query>",
            content_type="application/xml; charset=utf-8",
        )

    assert captured == {
        "content_type": "application/xml; charset=utf-8",
        "body": b"<query><id>42</id></query>",
    }
    assert response.code == "0000"
    assert [item.id for item in response.items.item] == [1, 2]
    assert [item.name for item in response.items.item] == ["first", "second"]


def test_invalid_xml_response_is_wrapped_as_external_service_error() -> None:
    with HttpClient(
        HttpClientConfig(base_url="https://example.test"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=b"<response>",
                headers={"Content-Type": "application/xml"},
            )
        ),
    ) as client:
        with pytest.raises(ExternalServiceError, match="invalid XML response"):
            client.request("GET", "/xml", response_model=Response)


def test_xml_response_rejects_dtd_and_entity_declarations() -> None:
    xml = b'<!DOCTYPE response [<!ENTITY value "0000">]><response><code>&value;</code></response>'
    with HttpClient(
        HttpClientConfig(base_url="https://example.test"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=xml,
                headers={"Content-Type": "application/xml"},
            )
        ),
    ) as client:
        with pytest.raises(ExternalServiceError, match="must not contain DTD"):
            client.request("GET", "/xml", response_model=Response)


def test_raw_body_rejects_other_request_body_types() -> None:
    with HttpClient(HttpClientConfig(base_url="https://example.test")) as client:
        with pytest.raises(ValueError, match="raw_body"):
            client.request(
                "POST",
                "/xml",
                response_model=Response,
                raw_body="<query />",
                form_data={"key": "value"},
            )
