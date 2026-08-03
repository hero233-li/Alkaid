import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.workbench.models import WorkbenchHistory, WorkbenchPackage
from apps.workbench.schemas import WorkbenchRequest
from apps.workbench.use_cases import execute_workbench_request


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


def saz_file() -> SimpleUploadedFile:
    content = BytesIO()
    with ZipFile(content, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "raw/1_c.txt",
            b"POST https://service.example/api/customer?active=1 HTTP/1.1\r\n"
            b"Host: service.example\r\n"
            b"Content-Type: application/json; charset=utf-8\r\n"
            b"Content-Length: 17\r\n"
            b"Authorization: Bearer imported-token\r\n\r\n"
            b'{"name":"test"}',
        )
        archive.writestr(
            "raw/1_s.txt",
            b"HTTP/1.1 201 Created\r\n"
            b"Content-Type: application/json\r\n"
            b"X-Result: created\r\n\r\n"
            b'{"id":7}',
        )
        archive.writestr(
            "raw/2_c.txt",
            b"POST /form HTTP/1.1\r\n"
            b"Host: service.example:443\r\n"
            b"Content-Type: application/x-www-form-urlencoded\r\n\r\n"
            b"action=create&id=7",
        )
        archive.writestr("raw/2_s.txt", b"HTTP/1.1 204 No Content\r\n\r\n")
    return SimpleUploadedFile(
        "customer-api.saz",
        content.getvalue(),
        content_type="application/octet-stream",
    )


@pytest.mark.django_db
def test_workbench_executes_request_and_persists_history() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.content == b'{"name":"test"}'
        return httpx.Response(201, json={"id": 7}, headers={"X-Result": "created"})

    outcome = execute_workbench_request(
        WorkbenchRequest.model_validate(request_payload()),
        transport=httpx.MockTransport(handler),
    )

    assert outcome.success is True
    assert outcome.status_code == 201
    assert json.loads(outcome.body) == {"id": 7}
    history = WorkbenchHistory.objects.get(pk=outcome.history_id)
    assert history.request_payload["bodyMode"] == "json"


@pytest.mark.django_db
def test_workbench_preserves_unsuccessful_http_response() -> None:
    result = execute_workbench_request(
        WorkbenchRequest.model_validate(request_payload(method="GET", bodyMode="none", body="")),
        transport=httpx.MockTransport(lambda _request: httpx.Response(404, text="missing")),
    )
    assert result.success is False
    assert result.status_code == 404
    assert result.body == "missing"


@pytest.mark.django_db
def test_workbench_encodes_urlencoded_form_fields_for_httpx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        assert request.content == b"action=views_record&id=28247"
        return httpx.Response(200, text="ok")

    outcome = execute_workbench_request(
        WorkbenchRequest.model_validate(
            request_payload(
                url="https://service.example/wp-admin/admin-ajax.php",
                headers={},
                bodyMode="form-urlencoded",
                body="",
                formFields=[
                    {"id": "action", "name": "action", "value": "views_record"},
                    {"id": "post-id", "name": "id", "value": "28247"},
                ],
            )
        ),
        transport=httpx.MockTransport(handler),
    )

    assert outcome.success is True
    assert outcome.status_code == 200


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
def test_saz_import_creates_package_tree_and_request_details(client) -> None:
    imported = client.post("/api/workbench/packages/import-saz", {"file": saz_file()})

    assert imported.status_code == 201
    package = imported.json()["data"]
    assert package["name"] == "customer-api"
    assert package["requestCount"] == 2
    assert [item["method"] for item in package["requests"]] == ["POST", "POST"]
    assert package["requests"][1]["url"] == "https://service.example:443/form"

    listed = client.get("/api/workbench/packages")
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == package["id"]

    request_id = package["requests"][0]["id"]
    detail = client.get(f"/api/workbench/packages/{package['id']}/requests/{request_id}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["requestPayload"]["bodyMode"] == "json"
    assert data["requestPayload"]["body"] == '{"name":"test"}'
    assert "Content-Length" not in data["requestPayload"]["headers"]
    assert data["requestPayload"]["headers"]["Authorization"] == "Bearer imported-token"
    assert data["response"]["statusCode"] == 201
    assert data["response"]["body"] == '{"id":7}'

    deleted = client.delete(f"/api/workbench/packages/{package['id']}")
    assert deleted.status_code == 200
    assert not WorkbenchPackage.objects.exists()


@pytest.mark.django_db
def test_saz_import_rejects_invalid_archive_without_creating_package(client) -> None:
    upload = SimpleUploadedFile("invalid.saz", b"not-a-zip")

    response = client.post("/api/workbench/packages/import-saz", {"file": upload})

    assert response.status_code == 400
    assert "有效" in response.json()["message"]
    assert not WorkbenchPackage.objects.exists()


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


@pytest.mark.django_db
@override_settings(WORKBENCH_ALLOWED_HOSTS=("localhost",))
def test_workbench_rejects_localhost_even_if_listed() -> None:
    with pytest.raises(ValueError, match="内部或保留地址"):
        execute_workbench_request(
            WorkbenchRequest.model_validate(request_payload(url="http://localhost:8000/internal")),
            transport=httpx.MockTransport(lambda request: httpx.Response(200)),
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    (
        "https://unlisted-public.example/api",
        "http://localhost:8000/internal",
        "http://198.18.0.182/internal",
    ),
)
@override_settings(WORKBENCH_ALLOWED_HOSTS=("*",))
def test_workbench_wildcard_allows_every_host_and_address(url: str) -> None:
    outcome = execute_workbench_request(
        WorkbenchRequest.model_validate(request_payload(url=url)),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="ok")),
    )

    assert outcome.status_code == 200


@pytest.mark.django_db
@override_settings(WORKBENCH_ALLOWED_HOSTS=("service.example", "127.0.0.1"))
def test_workbench_rejects_redirect_to_forbidden_address() -> None:
    with pytest.raises(ValueError, match="内部或保留地址"):
        execute_workbench_request(
            WorkbenchRequest.model_validate(request_payload(bodyMode="none", body="")),
            transport=httpx.MockTransport(
                lambda request: httpx.Response(302, headers={"Location": "http://127.0.0.1/admin"})
            ),
        )


@pytest.mark.django_db
def test_sensitive_headers_are_not_sent_or_persisted() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.headers))
        return httpx.Response(200, headers={"Set-Cookie": "secret=1"}, text="ok")

    result = execute_workbench_request(
        WorkbenchRequest.model_validate(
            request_payload(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer secret",
                    "Cookie": "token=secret",
                    "X-Token": "secret",
                }
            )
        ),
        transport=httpx.MockTransport(handler),
    )
    history = WorkbenchHistory.objects.get(pk=result.history_id)
    persisted = {name.lower() for name in history.request_headers}
    assert not persisted & {"authorization", "cookie", "x-token"}
    assert "set-cookie" not in {name.lower() for name in history.response_headers}
    assert "authorization" not in captured
    assert "cookie" not in captured
