from apps.integrations.cjdk_jyrc.client import CjdkJyrcClient
from apps.product_data.product_applications.contracts import SessionState


class CjdkExternalSessionGateway:
    def __init__(self, client: CjdkJyrcClient) -> None:
        self._client = client

    def initialize_session(self, application_url: str) -> SessionState:
        return self._client.acquire_session(application_url)

    def session_state(self) -> SessionState:
        return self._client.state
