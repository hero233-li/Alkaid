from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.java_gateway import JavaApplicationLinkGateway
from apps.integrations.cjdk_jyrc.request_builder import build_application_link_request
from apps.integrations.cjdk_jyrc.url_policy import validate_external_url
from apps.product_data.product_applications.contracts import (
    ApplicationLinkCommand,
    ApplicationLinksResult,
    FrozenApplicationLinkRoute,
)


class CjdkApplicationLinkGateway:
    def __init__(
        self,
        *,
        settings: config.CjdkJyrcSettings,
        java_gateway: JavaApplicationLinkGateway,
    ) -> None:
        self._settings = settings
        self._java_gateway = java_gateway

    def generate_application_link(self, command: ApplicationLinkCommand) -> ApplicationLinksResult:
        request = build_application_link_request(
            plan=FrozenApplicationLinkRoute.model_validate(command.plan),
            normalized_payload=dict(command.normalized_payload),
        )
        links = self._java_gateway.generate_link(request)
        policy = self._settings.environment(request.env).url_policy
        validate_external_url(links.internal_url, policy)
        validate_external_url(links.external_url, policy)
        return ApplicationLinksResult(
            internal_url=links.internal_url,
            external_url=links.external_url,
        )
