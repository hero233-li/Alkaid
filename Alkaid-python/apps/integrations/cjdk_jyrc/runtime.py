from __future__ import annotations

from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.agreement_gateway import CjdkAgreementGateway
from apps.integrations.cjdk_jyrc.application_link_gateway import CjdkApplicationLinkGateway
from apps.integrations.cjdk_jyrc.client import CjdkJyrcClient
from apps.integrations.cjdk_jyrc.java_gateway import JavaApplicationLinkGateway
from apps.integrations.cjdk_jyrc.session_gateway import CjdkExternalSessionGateway
from apps.integrations.contracts import IntegrationObserver


class CjdkJyrcRuntime:
    """Compose shared CJDK infrastructure and own only its lifetime."""

    def __init__(
        self,
        *,
        settings: config.CjdkJyrcSettings,
        observer: IntegrationObserver,
        trace_id: str,
        environment: str,
    ) -> None:
        client = CjdkJyrcClient(
            settings=settings,
            observer=observer,
            trace_id=trace_id,
            environment=environment,
        )
        java_gateway = JavaApplicationLinkGateway(observer=observer, trace_id=trace_id)
        self._client = client
        self.application_links = CjdkApplicationLinkGateway(
            settings=settings,
            java_gateway=java_gateway,
        )
        self.external_session = CjdkExternalSessionGateway(client)
        self.agreements = CjdkAgreementGateway(settings=settings, client=client)

    def __enter__(self) -> CjdkJyrcRuntime:
        self._client.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._client.__exit__(*args)
