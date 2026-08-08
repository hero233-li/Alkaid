import httpx

from apps.integrations.mock import MockTransportRouter


def test_public_mock_router_supports_independent_feature_scenarios() -> None:
    first = MockTransportRouter().register(
        "POST",
        "/execute",
        lambda request: MockTransportRouter.json_response(
            {
                "feature": "first",
                "request": MockTransportRouter.parse_json_form_field(request, "data"),
            }
        ),
    )
    second = MockTransportRouter().register(
        "POST",
        "/execute",
        lambda request: MockTransportRouter.json_response(
            {
                "feature": "second",
                "request": MockTransportRouter.parse_json_form_field(request, "data"),
            }
        ),
    )

    with httpx.Client(base_url="https://first.mock", transport=first.transport()) as client:
        first_response = client.post("/execute", data={"data": '{"value": 1}'})
    with httpx.Client(base_url="https://second.mock", transport=second.transport()) as client:
        second_response = client.post("/execute", data={"data": '{"value": 2}'})

    assert first_response.json() == {"feature": "first", "request": {"value": 1}}
    assert second_response.json() == {"feature": "second", "request": {"value": 2}}
