from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.java_gateway import JavaApplicationLinkGateway
from apps.integrations.cjdk_jyrc.request_builder import build_application_link_request
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
        # Java 返回内外网两个地址；真正选中的地址在 Session 初始化时按对应环境策略校验。
        return ApplicationLinksResult(
            internal_url=links.internal_url,
            external_url=links.external_url,
        )
