import json
from unittest.mock import patch

import pytest
from django.test import Client

from apps.workflows.models import WorkflowRun


@pytest.mark.django_db(transaction=True)
def test_start_and_query_workflow():
    client = Client()
    with patch("apps.workflows.views.execute_workflow.delay") as delay:
        response = client.post(
            "/api/workflows/",
            data=json.dumps({"input": {"value": "  hello   world "}}),
            content_type="application/json",
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["created"] is True
    delay.assert_called_once_with(payload["workflow_id"])

    status_response = client.get(f"/api/workflows/{payload['workflow_id']}/")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "pending"


@pytest.mark.django_db(transaction=True)
def test_idempotency_key_returns_existing_workflow_without_enqueuing_again():
    client = Client()
    body = json.dumps({"input": {"value": "hello"}, "idempotency_key": "submission-1"})
    with patch("apps.workflows.views.execute_workflow.delay") as delay:
        first = client.post("/api/workflows/", data=body, content_type="application/json")
        second = client.post("/api/workflows/", data=body, content_type="application/json")

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["workflow_id"] == second.json()["workflow_id"]
    assert second.json()["created"] is False
    assert delay.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_idempotency_key_rejects_different_input():
    client = Client()
    with patch("apps.workflows.views.execute_workflow.delay"):
        first = client.post(
            "/api/workflows/",
            data=json.dumps({"input": {"value": "first"}, "idempotency_key": "submission-2"}),
            content_type="application/json",
        )
        second = client.post(
            "/api/workflows/",
            data=json.dumps({"input": {"value": "second"}, "idempotency_key": "submission-2"}),
            content_type="application/json",
        )

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"


@pytest.mark.django_db
def test_invalid_request_is_rejected_without_creating_state():
    response = Client().post(
        "/api/workflows/",
        data=json.dumps({"input": {"value": ""}}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert WorkflowRun.objects.count() == 0
