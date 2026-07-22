import json

import pytest

from apps.portal.models import PortalPreference, ReleaseNote


@pytest.mark.django_db
def test_release_management_crud(client) -> None:
    created = client.post(
        "/api/portal/releases",
        data=json.dumps({"version": " v1.0.0 ", "content": " 首次发布 "}),
        content_type="application/json",
    )
    assert created.status_code == 201
    assert created.json()["data"]["version"] == "v1.0.0"

    release_id = created.json()["data"]["id"]
    updated = client.put(
        f"/api/portal/releases/{release_id}",
        data=json.dumps({"version": "v1.0.1", "content": "修订说明"}),
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["content"] == "修订说明"
    assert client.get("/api/portal/releases").json()["data"][0]["version"] == "v1.0.1"

    deleted = client.delete(f"/api/portal/releases/{release_id}")
    assert deleted.status_code == 200
    assert not ReleaseNote.objects.exists()


@pytest.mark.django_db
def test_portal_menu_preferences_are_persisted_and_deduplicated(client) -> None:
    saved = client.put(
        "/api/portal/home-shortcuts",
        data=json.dumps({"menuKeys": ["product-application", "product-application", "workbench"]}),
        content_type="application/json",
    )
    assert saved.status_code == 200
    assert saved.json()["data"] == ["product-application", "workbench"]
    assert client.get("/api/portal/home-shortcuts").json()["data"] == [
        "product-application",
        "workbench",
    ]


@pytest.mark.django_db
def test_hidden_menus_cannot_hide_home_or_system_settings(client) -> None:
    response = client.put(
        "/api/portal/hidden-menus",
        data=json.dumps({"menuKeys": ["home", "settings", "workbench"]}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["data"] == ["workbench"]
    assert PortalPreference.objects.get(key="hidden_menus").value == ["workbench"]


@pytest.mark.django_db
def test_portal_rejects_invalid_menu_keys(client) -> None:
    response = client.put(
        "/api/portal/hidden-menus",
        data=json.dumps({"menuKeys": ["invalid/menu"]}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_submission"
