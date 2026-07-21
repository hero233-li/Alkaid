import json
from urllib.parse import parse_qs

import httpx
import pytest

import apps.integrations.product_system.application_link as application_link_module
from apps.integrations.application_link.models import GenerateApplicationLinkRequest
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


def _request(category: str) -> GenerateApplicationLinkRequest:
    return GenerateApplicationLinkRequest(
        env="env-1",
        product="product-b",
        category=category,
        cooperation_project_id="PROJECT-001",
        payload={"loanType": "首贷", "customerPhone": "13800138000"},
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("category", "expected_path"),
    [("太阳码", "/links/sun-code"), ("动态链接", "/links/dynamic")],
)
def test_generate_link_uses_one_five_field_form_and_returns_two_urls(
    monkeypatch, category: str, expected_path: str
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
        HttpClientConfig(
            base_url="https://application-link.example",
            token="secret-token",
            max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(
        application_link_module,
        "create_product_system_client",
        lambda service, environment=None: client,
    )
    monkeypatch.setattr(application_link_module, "_configured_sign", lambda message: "test-sign")

    job = _job()
    result = application_link_module.generate_application_link(job, _request(category))

    assert len(captured) == 1
    assert captured[0].method == "POST"
    assert captured[0].url.path == expected_path
    assert captured[0].headers["content-type"].startswith("application/x-www-form-urlencoded")
    form = parse_qs(captured[0].content.decode(), keep_blank_values=True)
    assert set(form) == {"msg_id", "sign", "timestamp", "REQ_MESSAGE", "biz_content"}
    assert form["msg_id"] == [job.trace_id]
    assert form["sign"] == ["test-sign"]
    assert form["REQ_MESSAGE"] == form["biz_content"]
    message = json.loads(form["REQ_MESSAGE"][0])
    assert message["REQ_BODY"]["request"] == {
        "env": "env-1",
        "product": "product-b",
        "category": category,
        "cooperationProjectId": "PROJECT-001",
        "payload": {"loanType": "首贷", "customerPhone": "13800138000"},
    }
    assert result.internal_url == "https://internal.example/link"
    assert result.external_url == "https://external.example/link"

    call = job.api_calls.get()
    assert call.status == ApiCallStatus.SUCCESS
    assert call.request_body["form"]["sign"] == "te***gn"
    assert call.request_body["form"]["REQ_MESSAGE"] != form["REQ_MESSAGE"][0]
    assert call.request_headers["authorization"] == "Be***en"


@pytest.mark.django_db
def test_generate_link_records_business_error(monkeypatch) -> None:
    client = HttpClient(
        HttpClientConfig(base_url="https://application-link.example", max_retries=0),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "code": "9999",
                    "data": {
                        "internal_url": "https://internal.example/rejected",
                        "external_url": "https://external.example/rejected",
                    },
                },
            )
        ),
    )
    monkeypatch.setattr(
        application_link_module,
        "create_product_system_client",
        lambda service, environment=None: client,
    )

    job = _job()
    with pytest.raises(BusinessResponseError):
        application_link_module.generate_application_link(job, _request("太阳码"))

    call = job.api_calls.get()
    assert call.status == ApiCallStatus.FAILED
    assert call.error_type == "BusinessResponseError"


@pytest.mark.django_db
def test_generate_link_rejects_conflicting_payload_authority() -> None:
    with pytest.raises(ValueError, match="payload.*env"):
        GenerateApplicationLinkRequest(
            env="env-1",
            product="product-b",
            category="太阳码",
            payload={"env": "env-2"},
        )
