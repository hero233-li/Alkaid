import json

import httpx
import pytest

import apps.integrations.application_link.adapter as adapter_module
from apps.integrations.application_link.adapter import ApplicationLinkAdapter
from apps.integrations.application_link.models import (
    CreateApplicationRequest,
    GenerateLinksRequest,
)
from apps.integrations.contracts import BusinessResponseError
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.jobs.models import ApiCallStatus
from apps.jobs.services import create_job


def _job():
    return create_job(
        kind="application_link_generation",
        name="申请链接协议测试",
        product="product-b",
        payload={},
        trace_id="trace-application-link-contract",
        idempotency_key="application-link-contract",
        timeout_seconds=60,
    ).job


@pytest.mark.django_db
def test_application_link_adapter_records_wire_contract_and_masks_secrets(
    monkeypatch,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"code": "0000", "data": {"application_no": "APP-001"}},
        )

    client = HttpClient(
        HttpClientConfig(
            base_url="https://application-link.example",
            token="secret-token",
            max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(adapter_module, "_create_client", lambda: client)

    job = _job()
    with ApplicationLinkAdapter(job) as adapter:
        result = adapter.create_application(
            CreateApplicationRequest(
                product="product-b",
                category="太阳码",
                payload={"customerPhone": "13800138000"},
            )
        )

    assert result.application_no == "APP-001"
    assert captured[0].method == "POST"
    assert captured[0].url.path == "/applications"
    assert json.loads(captured[0].content)["product"] == "product-b"
    assert captured[0].headers["authorization"] == "Bearer secret-token"

    call = job.api_calls.get()
    assert call.status == ApiCallStatus.SUCCESS
    assert call.request_headers["authorization"] == "Be***en"
    assert call.request_body["body"]["payload"]["customerPhone"] == "13***00"
    assert call.response_body["data"]["application_no"] == "APP-001"


@pytest.mark.django_db
def test_application_link_adapter_records_business_error(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": "9999", "data": {"application_no": "REJECTED"}},
        )

    client = HttpClient(
        HttpClientConfig(
            base_url="https://application-link.example",
            max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(adapter_module, "_create_client", lambda: client)

    job = _job()
    with pytest.raises(BusinessResponseError), ApplicationLinkAdapter(job) as adapter:
        adapter.create_application(
            CreateApplicationRequest(product="product-b", category="太阳码", payload={})
        )

    call = job.api_calls.get()
    assert call.status == ApiCallStatus.FAILED
    assert call.error_type == "BusinessResponseError"
    assert call.response_body["code"] == "9999"


@pytest.mark.django_db
def test_application_link_adapter_rejects_unknown_category(monkeypatch) -> None:
    client = HttpClient(
        HttpClientConfig(base_url="https://application-link.example", max_retries=0),
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    monkeypatch.setattr(adapter_module, "_create_client", lambda: client)

    with pytest.raises(ValueError, match="未知申请链接类别"), ApplicationLinkAdapter(
        _job()
    ) as adapter:
        adapter.generate_links(
            GenerateLinksRequest(
                application_no="APP-001",
                product="product-b",
                category="未知类别",
            ),
            category="未知类别",
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("category", "expected_path"),
    [("太阳码", "/links/sun-code"), ("动态链接", "/links/dynamic")],
)
def test_application_link_generate_links_wire_contract(
    monkeypatch,
    category: str,
    expected_path: str,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "code": "0000",
                "data": {
                    "internal_url": "https://internal.example/link",
                    "external_url": "https://external.example/link",
                },
            },
        )

    client = HttpClient(
        HttpClientConfig(base_url="https://application-link.example", max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(adapter_module, "_create_client", lambda: client)

    job = _job()
    with ApplicationLinkAdapter(job) as adapter:
        result = adapter.generate_links(
            GenerateLinksRequest(
                application_no="APP-001",
                product="product-b",
                category=category,
            ),
            category=category,
        )

    assert captured[0].url.path == expected_path
    assert json.loads(captured[0].content) == {
        "application_no": "APP-001",
        "product": "product-b",
        "category": category,
    }
    assert result.internal_url == "https://internal.example/link"
    assert result.external_url == "https://external.example/link"
