import json
from urllib.parse import parse_qs

import httpx

from apps.integrations.contracts import (
    AuthSpec,
    EndpointSpec,
    TokenSource,
    TokenUpdateSpec,
)
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.integrations.mock_product.models import LoginResponse, OperationResponse

FLOW_PROVIDER = "product_flow"
FIXED_PROVIDER = "fixed_external"

LOGIN = EndpointSpec(
    operation_id="mock_product.login",
    method="POST",
    path="/auth/token",
    response_model=LoginResponse,
    token_update=TokenUpdateSpec(
        provider=FLOW_PROVIDER,
        source=TokenSource.RESPONSE_BODY,
        path="data.token",
    ),
)

PRODUCT_CHECKS = {
    "product-a": EndpointSpec(
        operation_id="mock_product.whitelist_check",
        method="POST",
        path="/checks/whitelist",
        response_model=OperationResponse,
        auth=AuthSpec(provider=FLOW_PROVIDER),
        success_path="code",
        success_values=("0000",),
    ),
    "product-b": EndpointSpec(
        operation_id="mock_product.red_shield_check",
        method="POST",
        path="/checks/red-shield",
        response_model=OperationResponse,
        auth=AuthSpec(provider=FLOW_PROVIDER),
        success_path="code",
        success_values=("0000",),
    ),
    "product-c": EndpointSpec(
        operation_id="mock_product.credit_check",
        method="POST",
        path="/checks/credit",
        response_model=OperationResponse,
        auth=AuthSpec(provider=FLOW_PROVIDER),
        success_path="code",
        success_values=("0000",),
    ),
}

ROTATE_TOKEN = EndpointSpec(
    operation_id="mock_product.rotate_token",
    method="POST",
    path="/auth/rotate",
    response_model=OperationResponse,
    auth=AuthSpec(provider=FLOW_PROVIDER),
    token_update=TokenUpdateSpec(
        provider=FLOW_PROVIDER,
        source=TokenSource.RESPONSE_HEADER,
        path="X-New-Token",
    ),
    success_path="code",
    success_values=("0000",),
)

SUBMIT_APPLICATION = EndpointSpec(
    operation_id="mock_product.submit_application",
    method="POST",
    path="/applications",
    response_model=OperationResponse,
    auth=AuthSpec(provider=FLOW_PROVIDER),
    success_path="code",
    success_values=("0000",),
)

FIXED_AUDIT = EndpointSpec(
    operation_id="fixed_external.audit",
    method="POST",
    path="/fixed/audit",
    response_model=OperationResponse,
    auth=AuthSpec(provider=FIXED_PROVIDER, header="X-Api-Token", prefix=""),
    success_path="code",
    success_values=("0000",),
)

ENDPOINT_SPECS = {
    endpoint.operation_id: endpoint
    for endpoint in (
        LOGIN,
        *PRODUCT_CHECKS.values(),
        ROTATE_TOKEN,
        SUBMIT_APPLICATION,
        FIXED_AUDIT,
    )
}


def create_mock_http_client(fixed_token: str) -> HttpClient:
    state = {"flow_token": "flow-token-v1"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = _request_payload(request)
        if path == "/auth/token":
            return httpx.Response(200, json={"data": {"token": state["flow_token"]}})

        if path == "/fixed/audit":
            if request.headers.get("X-Api-Token") != fixed_token:
                return httpx.Response(401, json={"code": "UNAUTHORIZED"})
            return httpx.Response(
                200,
                json={"code": "0000", "message": "固定 Token 校验成功", "data": payload},
            )

        expected = f"Bearer {state['flow_token']}"
        if request.headers.get("Authorization") != expected:
            return httpx.Response(401, json={"code": "UNAUTHORIZED"})
        if path == "/auth/rotate":
            state["flow_token"] = "flow-token-v2"
            return httpx.Response(
                200,
                headers={"X-New-Token": state["flow_token"]},
                json={"code": "0000", "message": "Token 已更新", "data": payload},
            )
        if path.startswith("/checks/"):
            return httpx.Response(
                200,
                json={"code": "0000", "message": "产品检查通过", "data": payload},
            )
        if path.startswith("/applications"):
            return httpx.Response(
                200,
                json={
                    "code": "0000",
                    "message": "产品申请成功",
                    "data": {"applicationNo": "MOCK-APPLICATION-001"},
                },
            )
        return httpx.Response(404, json={"code": "NOT_FOUND"})

    return HttpClient(
        HttpClientConfig(base_url="https://mock-product.local", max_retries=0),
        transport=httpx.MockTransport(handler),
    )


def _request_payload(request: httpx.Request) -> dict[str, object]:
    content = request.content.decode("utf-8") if request.content else ""
    if "application/x-www-form-urlencoded" in request.headers.get("Content-Type", ""):
        parsed = parse_qs(content, keep_blank_values=True)
        result: dict[str, object] = {}
        for name, values in parsed.items():
            value = values[-1]
            try:
                result[name] = json.loads(value)
            except json.JSONDecodeError:
                result[name] = value
        return result
    return json.loads(content or "{}")
