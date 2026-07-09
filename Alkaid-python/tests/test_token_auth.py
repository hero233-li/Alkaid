import httpx
import pytest

from apps.integrations.auth import (
    FlowTokenProvider,
    StaticTokenProvider,
    TokenManager,
    TokenUnavailable,
    TokenUpdateError,
)
from apps.integrations.contracts import (
    AuthSpec,
    BusinessResponseError,
    EndpointSpec,
    HttpResult,
    TokenSource,
    TokenUpdateSpec,
)
from apps.integrations.executor import EndpointExecutor
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.integrations.mock_product.models import OperationResponse


def result(*, body, headers=None):
    return HttpResult(
        data=OperationResponse(code="0000", message="ok"),
        status_code=200,
        headers=headers or {},
        body=body,
    )


def test_flow_token_is_scoped_and_only_changes_for_explicit_update_specs():
    manager = TokenManager({"flow": FlowTokenProvider()})
    auth = AuthSpec(provider="flow")

    with pytest.raises(TokenUnavailable, match="尚未获取"):
        manager.build_headers(auth)

    manager.apply_update(
        TokenUpdateSpec(
            provider="flow",
            source=TokenSource.RESPONSE_BODY,
            path="data.token",
        ),
        result(body={"data": {"token": "token-v1"}}),
    )
    assert manager.build_headers(auth) == {"Authorization": "Bearer token-v1"}
    assert manager.state("flow").version == 1

    manager.apply_update(None, result(body={"data": {"token": "must-not-update"}}))
    assert manager.state("flow").value == "token-v1"
    assert manager.state("flow").version == 1

    manager.apply_update(
        TokenUpdateSpec(
            provider="flow",
            source=TokenSource.RESPONSE_HEADER,
            path="X-New-Token",
        ),
        result(body={}, headers={"x-new-token": "token-v2"}),
    )
    assert manager.state("flow").value == "token-v2"
    assert manager.state("flow").version == 2


def test_static_token_uses_custom_header_and_cannot_be_updated():
    provider = StaticTokenProvider("fixed-token")
    manager = TokenManager({"fixed": provider})

    assert manager.build_headers(AuthSpec(provider="fixed", header="X-Api-Token", prefix="")) == {
        "X-Api-Token": "fixed-token"
    }
    with pytest.raises(TokenUpdateError, match="固定 Token"):
        provider.update("new-token")


def test_business_failure_does_not_update_flow_token():
    flow = FlowTokenProvider()
    flow.update("old-token")
    manager = TokenManager({"flow": flow})
    endpoint = EndpointSpec(
        operation_id="test.business_failure",
        method="POST",
        path="/business-failure",
        response_model=OperationResponse,
        auth=AuthSpec(provider="flow"),
        token_update=TokenUpdateSpec(
            provider="flow",
            source=TokenSource.RESPONSE_BODY,
            path="data.token",
        ),
        success_path="code",
        success_values=("0000",),
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "code": "BUSINESS_ERROR",
                "message": "业务失败",
                "data": {"token": "must-not-update"},
            },
        )
    )

    with HttpClient(
        HttpClientConfig(base_url="https://example.test", max_retries=0),
        transport=transport,
    ) as client:
        with pytest.raises(BusinessResponseError, match="业务处理失败"):
            EndpointExecutor(client, manager).execute(
                endpoint,
                trace_id="business-failure",
            )

    assert manager.state("flow").value == "old-token"
    assert manager.state("flow").version == 1
