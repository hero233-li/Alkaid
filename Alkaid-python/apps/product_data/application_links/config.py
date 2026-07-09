from dataclasses import dataclass

from apps.product_data.application_links.schemas import LinkCategory

APPLICATION_LINK_CONFIG_VERSION = 1


@dataclass(frozen=True)
class ApplicationLinkRoute:
    handler: str
    required_fields: tuple[str, ...] = ()


DYNAMIC_CUSTOMER_FIELDS = (
    "customerName",
    "customerPhone",
    "customerCertificateNo",
    "customerCompanyName",
    "customerCompanyCode",
)

APPLICATION_LINK_ROUTES: dict[str, dict[str, dict[LinkCategory, ApplicationLinkRoute]]] = {
    "产品A": {
        "环境1": {
            LinkCategory.DYNAMIC_LINK: ApplicationLinkRoute(
                "product_a_dynamic_link_v1", DYNAMIC_CUSTOMER_FIELDS
            )
        },
        "环境2": {
            LinkCategory.DYNAMIC_LINK: ApplicationLinkRoute(
                "product_a_dynamic_link_v1", DYNAMIC_CUSTOMER_FIELDS
            )
        },
        "环境3": {LinkCategory.SUN_CODE: ApplicationLinkRoute("product_a_sun_code_v1")},
    },
    "产品B": {
        environment: {LinkCategory.SUN_CODE: ApplicationLinkRoute("product_b_sun_code_v1")}
        for environment in ("环境1", "环境2", "环境3")
    },
    "产品C": {
        environment: {
            LinkCategory.DYNAMIC_LINK: ApplicationLinkRoute(
                "product_c_dynamic_link_v1",
                (*DYNAMIC_CUSTOMER_FIELDS, "restoreStatus", "spcode"),
            )
        }
        for environment in ("环境1", "环境2", "环境3")
    },
}


class ApplicationLinkConfigurationError(ValueError):
    pass


def get_application_link_route(
    product: str,
    environment: str,
    category: LinkCategory,
) -> ApplicationLinkRoute:
    try:
        environment_routes = APPLICATION_LINK_ROUTES[product][environment]
    except KeyError:
        raise ApplicationLinkConfigurationError("当前环境下没有该产品") from None
    try:
        return environment_routes[category]
    except KeyError:
        raise ApplicationLinkConfigurationError("当前产品在该环境下不支持该类别") from None
