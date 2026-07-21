from typing import TYPE_CHECKING

from apps.core.errors import ConfigurationError
from apps.product_data.application_links.schemas import ApplicationLinkSubmission, LinkCategory

if TYPE_CHECKING:
    from apps.product_data.catalog_models import ProductCatalogSource, ProductReferenceData

ALL_METHODS = "*"


def validate_product_source(source: "ProductCatalogSource") -> None:
    method_codes = [method.code for method in source.applicationMethods]
    if len(method_codes) != len(set(method_codes)):
        raise ValueError("申请方式代码不能重复")
    if source.defaultApplicationMethod not in method_codes:
        raise ValueError("默认申请方式不存在")

    field_names = [field.name for field in source.fields]
    if len(field_names) != len(set(field_names)):
        raise ValueError("产品字段名称不能重复")
    if source.switchField not in field_names:
        raise ValueError("产品开关字段不存在")

    known_methods = set(method_codes)
    for field in source.fields:
        if field.required:
            raise ValueError(f"字段 {field.name} 请使用 requiredFor，不能同时维护 required")
        unknown_enabled = set(field.enabledFor) - known_methods - {ALL_METHODS}
        unknown_required = set(field.requiredFor) - known_methods - {ALL_METHODS}
        if unknown_enabled or unknown_required:
            raise ValueError(f"字段 {field.name} 引用了未知申请方式")
        for required_method in field.requiredFor:
            if required_method == ALL_METHODS:
                if ALL_METHODS not in field.enabledFor:
                    raise ValueError(f"字段 {field.name} 必填但并非所有申请方式启用")
            elif ALL_METHODS not in field.enabledFor and required_method not in field.enabledFor:
                raise ValueError(f"字段 {field.name} 在未启用的申请方式中被设为必填")
        if field.expose and not field.group:
            raise ValueError(f"页面字段 {field.name} 缺少 group")

    route_keys: list[tuple[str, str]] = []
    known_link_fields = set(ApplicationLinkSubmission.model_fields)
    known_categories = {category.value for category in LinkCategory}
    for route in source.features.applicationLinks:
        route_keys.append((route.environment, route.category))
        if route.category not in known_categories:
            raise ValueError(f"申请链接类别无效：{route.category}")
        unknown_required_fields = set(route.requiredFields) - known_link_fields
        if unknown_required_fields:
            raise ValueError(
                f"申请链接路由引用了未知字段：{', '.join(sorted(unknown_required_fields))}"
            )
    if len(route_keys) != len(set(route_keys)):
        raise ValueError("申请链接环境与类别路由不能重复")


def validate_catalog_environments(
    reference: "ProductReferenceData",
    products: dict[str, "ProductCatalogSource"],
) -> None:
    known_environments = {option.value for option in reference.environments}
    for product in products.values():
        unknown_product_environments = set(product.environments) - known_environments
        if unknown_product_environments:
            raise ConfigurationError(
                f"产品 {product.code} 引用了未知环境代码："
                f"{', '.join(sorted(unknown_product_environments))}"
            )
        unknown_link_environments = {
            route.environment for route in product.features.applicationLinks
        } - known_environments
        if unknown_link_environments:
            raise ConfigurationError(
                f"产品 {product.code} 的申请链接引用了未知环境代码："
                f"{', '.join(sorted(unknown_link_environments))}"
            )
