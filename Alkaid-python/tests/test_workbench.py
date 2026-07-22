import json

import httpx
import pytest
from django.test import override_settings

from apps.workbench.models import WorkbenchHistory
from apps.workbench.schemas import WorkbenchRequest
from apps.workbench.services import execute_request


def request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "method": "POST",
        "url": "https://service.example/items",
        "headers": {"Content-Type": "application/json"},
        "bodyMode": "json",
        "body": '{"name":"test"}',
        "formFields": [],
        "timeoutSeconds": 10,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_workbench_executes_request_and_persists_history() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.content == b'{"name":"test"}'
        return httpx.Response(201, json={"id": 7}, headers={"X-Result": "created"})

    result = execute_request(
        WorkbenchRequest.model_validate(request_payload()),
        transport=httpx.MockTransport(handler),
    )

    assert result["success"] is True
    assert result["statusCode"] == 201
    assert json.loads(result["body"]) == {"id": 7}
    history = WorkbenchHistory.objects.get(pk=result["historyId"])
    assert history.request_payload["bodyMode"] == "json"


@pytest.mark.django_db
def test_workbench_preserves_unsuccessful_http_response() -> None:
    result = execute_request(
        WorkbenchRequest.model_validate(request_payload(method="GET", bodyMode="none", body="")),
        transport=httpx.MockTransport(lambda _request: httpx.Response(404, text="missing")),
    )
    assert result["success"] is False
    assert result["statusCode"] == 404
    assert result["body"] == "missing"


@pytest.mark.django_db
def test_workbench_history_can_be_listed_renamed_and_deleted(client) -> None:
    item = WorkbenchHistory.objects.create(
        name="GET example",
        method="GET",
        url="https://example.com",
        request_headers={},
        request_payload=request_payload(method="GET"),
    )

    listed = client.get("/api/workbench/history")
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == item.id

    renamed = client.post(
        f"/api/workbench/history/{item.id}/rename",
        data=json.dumps({"name": "健康检查"}),
        content_type="application/json",
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "健康检查"

    detail = client.get(f"/api/workbench/history/{item.id}")
    assert detail.json()["data"]["requestPayload"]["method"] == "GET"
    assert client.delete(f"/api/workbench/history/{item.id}").status_code == 200
    assert not WorkbenchHistory.objects.exists()


@pytest.mark.django_db
def test_workbench_rejects_non_http_url(client) -> None:
    response = client.post(
        "/api/workbench/execute",
        data=json.dumps(request_payload(url="file:///etc/passwd")),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_submission"


@pytest.mark.django_db
@override_settings(WORKBENCH_ENABLED=False)
def test_workbench_endpoint_is_unavailable_when_feature_is_disabled(client) -> None:
    response = client.get("/api/workbench/history")

    assert response.status_code == 404
    assert response.json()["code"] == "feature_disabled"
