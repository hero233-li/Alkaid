import json
import shutil
import subprocess
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.workflow.Documents.models import DocumentFolder, StoredDocument
from apps.workflow.Documents.word_import import (
    WordImportError,
    _conversion_backend,
    _office_binary,
    _run_conversion,
    convert_legacy_word_to_html,
)


def workspace_payload() -> dict:
    return {
        "folders": [
            {
                "id": "folder-root",
                "name": "项目资料",
                "parentId": None,
                "createdAt": "2026-08-02T10:00:00+08:00",
            },
            {
                "id": "folder-child",
                "name": "报表",
                "parentId": "folder-root",
                "createdAt": "2026-08-02T10:01:00+08:00",
            },
        ],
        "documents": [
            {
                "id": "document-1",
                "name": "月报.md",
                "content": "# 月报\n\n持久化内容",
                "size": 1,
                "kind": "document",
                "source": "created",
                "folderId": "folder-child",
                "createdAt": "2026-08-02T10:02:00+08:00",
                "updatedAt": "2026-08-02T10:03:00+08:00",
                "lastOpenedAt": "2026-08-02T10:04:00+08:00",
            }
        ],
    }


@pytest.mark.django_db
def test_workspace_is_persisted_and_loaded_from_database(client) -> None:
    response = client.put(
        "/api/documents/workspace",
        data=json.dumps(workspace_payload()),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert DocumentFolder.objects.count() == 2
    stored = StoredDocument.objects.get(pk="document-1")
    assert stored.folder_id == "folder-child"
    assert stored.content == "# 月报\n\n持久化内容"
    assert stored.size == len(stored.content.encode("utf-8"))

    loaded = client.get("/api/documents/workspace")
    assert loaded.status_code == 200
    assert loaded.json()["data"]["documents"][0]["name"] == "月报.md"
    loaded_folders = {item["id"]: item for item in loaded.json()["data"]["folders"]}
    assert loaded_folders["folder-child"]["parentId"] == "folder-root"


@pytest.mark.django_db
def test_document_can_be_read_updated_and_deleted(client) -> None:
    payload = workspace_payload()
    client.put(
        "/api/documents/workspace",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert client.get("/api/documents/document-1").json()["data"]["content"].startswith("# 月报")

    document = payload["documents"][0]
    document["name"] = "月报修订.md"
    document["content"] = "修订后的正文"
    updated = client.put(
        "/api/documents/document-1",
        data=json.dumps(document),
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "月报修订.md"
    assert StoredDocument.objects.get(pk="document-1").content == "修订后的正文"

    deleted = client.delete("/api/documents/document-1")
    assert deleted.status_code == 200
    assert not StoredDocument.objects.exists()


@pytest.mark.django_db
def test_folder_can_be_renamed_and_deleted(client) -> None:
    client.put(
        "/api/documents/workspace",
        data=json.dumps(workspace_payload()),
        content_type="application/json",
    )

    renamed = client.patch(
        "/api/documents/folders/folder-root",
        data=json.dumps({"name": "归档资料"}),
        content_type="application/json",
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "归档资料"

    deleted = client.delete("/api/documents/folders/folder-root")
    assert deleted.status_code == 200
    assert not DocumentFolder.objects.exists()
    assert StoredDocument.objects.get(pk="document-1").folder_id is None


@pytest.mark.django_db
def test_locked_document_is_read_only_until_unlocked(client) -> None:
    payload = workspace_payload()
    client.put(
        "/api/documents/workspace",
        data=json.dumps(payload),
        content_type="application/json",
    )

    locked = client.patch(
        "/api/documents/document-1",
        data=json.dumps({"locked": True}),
        content_type="application/json",
    )
    assert locked.status_code == 200
    assert locked.json()["data"]["locked"] is True
    assert client.get("/api/documents/document-1").status_code == 200

    updated = client.put(
        "/api/documents/document-1",
        data=json.dumps(payload["documents"][0] | {"content": "不能修改"}),
        content_type="application/json",
    )
    assert updated.status_code == 409
    assert updated.json()["code"] == "document_locked"
    assert client.delete("/api/documents/document-1").status_code == 409
    assert client.delete("/api/documents/folders/folder-root").status_code == 409
    assert (
        client.put(
            "/api/documents/workspace",
            data=json.dumps(payload),
            content_type="application/json",
        ).status_code
        == 409
    )

    touched = client.patch(
        "/api/documents/document-1",
        data=json.dumps({"lastOpenedAt": "2026-08-03T10:00:00+08:00"}),
        content_type="application/json",
    )
    assert touched.status_code == 200

    unlocked = client.patch(
        "/api/documents/document-1",
        data=json.dumps({"locked": False}),
        content_type="application/json",
    )
    assert unlocked.status_code == 200
    assert unlocked.json()["data"]["locked"] is False
    assert client.delete("/api/documents/document-1").status_code == 200


@pytest.mark.django_db
def test_workspace_rejects_invalid_folder_cycles_without_overwriting_data(client) -> None:
    valid = workspace_payload()
    client.put(
        "/api/documents/workspace",
        data=json.dumps(valid),
        content_type="application/json",
    )
    invalid = workspace_payload()
    invalid["folders"][0]["parentId"] = "folder-child"

    response = client.put(
        "/api/documents/workspace",
        data=json.dumps(invalid),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_submission"
    assert StoredDocument.objects.get(pk="document-1").name == "月报.md"


@pytest.mark.django_db
def test_online_word_is_persisted_as_an_editable_document(client) -> None:
    payload = workspace_payload()
    payload["documents"][0].update(
        {
            "name": "项目方案.docx",
            "content": "<h1>项目方案</h1><p>可编辑正文</p>",
            "kind": "word",
        }
    )

    response = client.put(
        "/api/documents/workspace",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200
    stored = StoredDocument.objects.get(pk="document-1")
    assert stored.kind == "word"
    assert "可编辑正文" in stored.content


@pytest.mark.django_db
def test_list_omits_content_and_single_document_crud_keeps_it(client) -> None:
    document = workspace_payload()["documents"][0]
    document["folderId"] = None

    created = client.post(
        "/api/documents/items",
        data=json.dumps(document),
        content_type="application/json",
    )
    assert created.status_code == 200
    assert created.json()["data"]["content"] == "# 月报\n\n持久化内容"

    listed = client.get("/api/documents/items")
    assert listed.status_code == 200
    assert "content" not in listed.json()["data"][0]

    detail = client.get("/api/documents/document-1")
    assert detail.json()["data"]["content"] == "# 月报\n\n持久化内容"

    moved = client.patch(
        "/api/documents/document-1",
        data=json.dumps({"folderId": None}),
        content_type="application/json",
    )
    assert moved.status_code == 200
    assert moved.json()["data"]["folderId"] is None

    deleted = client.delete("/api/documents/document-1")
    assert deleted.status_code == 200
    assert not StoredDocument.objects.exists()


@pytest.mark.django_db
def test_image_asset_is_stored_separately_and_attached_on_document_save(client) -> None:
    uploaded = client.post(
        "/api/documents/assets",
        data={"file": SimpleUploadedFile("diagram.png", b"\x89PNG\r\n", "image/png")},
    )
    assert uploaded.status_code == 200
    asset = uploaded.json()["data"]
    assert asset["url"].startswith("/api/documents/assets/")

    image_response = client.get(asset["url"])
    assert image_response.status_code == 200
    assert image_response.content == b"\x89PNG\r\n"
    assert image_response["Cache-Control"].endswith("immutable")

    document = workspace_payload()["documents"][0]
    document["folderId"] = None
    document["content"] = f'<p>示意图</p><img src="{asset["url"]}">'
    created = client.post(
        "/api/documents/items",
        data=json.dumps(document),
        content_type="application/json",
    )
    assert created.status_code == 200
    assert StoredDocument.objects.get(pk="document-1").assets.count() == 1


@pytest.mark.django_db
def test_inline_base64_image_is_externalized_before_persistence(client) -> None:
    document = workspace_payload()["documents"][0]
    document["folderId"] = None
    document["content"] = '<p>图片</p><img src="data:image/png;base64,iVBORw0KGgo=">'

    created = client.post(
        "/api/documents/items",
        data=json.dumps(document),
        content_type="application/json",
    )

    assert created.status_code == 200
    stored = StoredDocument.objects.get(pk="document-1")
    assert "data:image" not in stored.content
    assert "/api/documents/assets/" in stored.content
    assert stored.assets.count() == 1
    assert stored.size > len(stored.content.encode("utf-8"))


@pytest.mark.django_db
def test_legacy_doc_import_returns_editable_html(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.workflow.Documents.views.convert_legacy_word_to_html",
        lambda uploaded_file: f"<h1>{uploaded_file.name}</h1><p>转换后的正文</p>",
    )

    response = client.post(
        "/api/documents/import-word",
        data={"file": SimpleUploadedFile("旧文档.doc", b"legacy-word")},
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "旧文档.doc"
    assert "转换后的正文" in response.json()["data"]["html"]


def test_online_word_exports_a_real_docx_response(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.workflow.Documents.views.convert_html_to_docx",
        lambda html: b"PK\x03\x04docx-content" if "可编辑正文" in html else b"",
    )

    response = client.post(
        "/api/documents/export-word",
        data=json.dumps({"name": "项目方案.doc", "html": "<p>可编辑正文</p>"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.content.startswith(b"PK\x03\x04")
    assert response["Content-Type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ".docx" in response["Content-Disposition"]


def test_office_binary_uses_configured_path(monkeypatch, tmp_path: Path) -> None:
    binary = tmp_path / "soffice.exe"
    binary.write_bytes(b"")
    monkeypatch.setenv("LIBREOFFICE_BINARY", str(binary))

    assert _office_binary() == str(binary)


def test_windows_word_backend_uses_powershell_when_libreoffice_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "apps.workflow.Documents.word_import._office_binary",
        lambda: (_ for _ in ()).throw(WordImportError("missing")),
    )
    monkeypatch.setattr(
        "apps.workflow.Documents.word_import._word_powershell_binary",
        lambda: r"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
    )

    backend, binary = _conversion_backend()

    assert backend == "word"
    assert binary.endswith("powershell.exe")


def test_word_backend_uses_filtered_html_save_format(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr("apps.workflow.Documents.word_import.subprocess.run", fake_run)
    input_path = tmp_path / "input.doc"
    output_path = tmp_path / "input.html"

    _run_conversion(
        "word",
        "powershell.exe",
        input_path,
        output_path,
        tmp_path,
        export_docx=False,
    )

    command = captured["command"]
    assert isinstance(command, list)
    assert command[-2:] == ["-Format", "10"]
    assert (tmp_path / "convert-word.ps1").is_file()


@pytest.mark.skipif(shutil.which("textutil") is None, reason="macOS textutil is unavailable")
def test_textutil_fallback_opens_a_real_legacy_doc(monkeypatch, tmp_path: Path) -> None:
    source_text = tmp_path / "source.txt"
    source_text.write_text("无需安装 LibreOffice\n正文内容", encoding="utf-8")
    doc_path = tmp_path / "legacy.doc"
    subprocess.run(
        [
            shutil.which("textutil") or "textutil",
            "-convert",
            "doc",
            "-output",
            str(doc_path),
            str(source_text),
        ],
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(
        "apps.workflow.Documents.word_import._office_binary",
        lambda: (_ for _ in ()).throw(WordImportError("missing")),
    )
    upload = SimpleUploadedFile("legacy.doc", doc_path.read_bytes())

    html = convert_legacy_word_to_html(upload)

    assert "无需安装 LibreOffice" in html
    assert "正文内容" in html
