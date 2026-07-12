from apps.integrations.example_system.models import (
    ExampleEnvelope,
    ExampleLookupRequest,
    ExampleLookupResult,
)
from apps.integrations.http import HttpClient


class ExampleSystemAdapter:
    """The only module that knows the external system's wire format."""

    def __init__(self, client: HttpClient) -> None:
        self.client = client

    def lookup(self, request: ExampleLookupRequest, *, trace_id: str) -> ExampleLookupResult:
        response = self.client.request(
            "GET",
            "/v1/lookup",
            response_model=ExampleEnvelope,
            params={"value": request.value},
            trace_id=trace_id,
        )
        return ExampleLookupResult(
            reference=response.data.reference,
            display_value=response.data.display_value,
        )
