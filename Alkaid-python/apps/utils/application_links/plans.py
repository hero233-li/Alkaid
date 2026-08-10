from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from apps.utils.product_Conf.catalog import FrozenApplicationLinkRoute

from .contracts import ApplicationConfigurationError
from .profiles import load_integration_profile


def compile_application_link_plan(
    *,
    catalog: Any,
    product_code: str,
    environment: str,
    method_code: str,
    category_code: Any | None = None,
) -> FrozenApplicationLinkRoute:
    product = catalog.product(product_code)
    method = product.method(method_code)
    normalized_environment = environment.strip().upper()
    if normalized_environment not in product.environments:
        raise ApplicationConfigurationError(
            f"产品 {product.code} 不支持环境：{normalized_environment}"
        )
    matches = [
        route
        for route in product.features.application_links
        if route.environment == normalized_environment
        and ("*" in route.application_methods or method.code in route.application_methods)
        and (category_code is None or route.category_code == category_code)
    ]
    category_message = (
        f"、类别 {getattr(category_code, 'display_name', category_code)}"
        if category_code is not None
        else ""
    )
    if not matches:
        raise ApplicationConfigurationError(
            f"产品 {product.code} 在环境 {normalized_environment}、"
            f"申请方式 {method.code}{category_message} 未配置申请链接路由"
        )
    if len(matches) > 1:
        raise ApplicationConfigurationError(
            f"产品 {product.code} 在环境 {normalized_environment}、"
            f"申请方式 {method.code}{category_message} 匹配到多条申请链接路由"
        )
    route = matches[0]
    try:
        profile = load_integration_profile(
            route.integration_profile_id,
            route.integration_profile_version,
        )
    except ValueError as exc:
        raise ApplicationConfigurationError(str(exc)) from exc
    enabled_fields = {field.name for field in product.enabled_execution_fields(method.code)}
    unknown_required = set(route.required_fields) - enabled_fields
    if unknown_required:
        raise ApplicationConfigurationError(
            f"路由 {route.route_id} 的必填字段未在当前产品/申请方式启用："
            f"{', '.join(sorted(unknown_required))}"
        )
    for secret_path in profile.secret_bindings:
        if not _path_exists(profile.template, secret_path):
            raise ApplicationConfigurationError(
                f"Profile {profile.id}@{profile.version} 的秘密字段路径不存在：{secret_path}"
            )
        if _path_exists(route.request_template, secret_path):
            raise ApplicationConfigurationError(
                f"路由 {route.route_id} 不允许覆盖秘密字段：{secret_path}"
            )
    compiled_template = deepcopy(profile.template)
    _deep_merge(compiled_template, route.request_template)
    for secret_path in profile.secret_bindings:
        if not _path_exists(compiled_template, secret_path):
            raise ApplicationConfigurationError(
                f"路由 {route.route_id} 破坏了秘密字段路径：{secret_path}"
            )
    for target, source in route.payload_bindings.items():
        overlapping_secret = next(
            (
                secret_path
                for secret_path in profile.secret_bindings
                if _paths_overlap(target, secret_path)
            ),
            None,
        )
        if overlapping_secret:
            raise ApplicationConfigurationError(
                f"路由 {route.route_id} 的 payloadBindings 不允许覆盖秘密字段："
                f"{overlapping_secret}"
            )
        _validate_binding_source(source, enabled_fields, route.route_id)
        if not _path_parent_exists(compiled_template, target):
            raise ApplicationConfigurationError(
                f"路由 {route.route_id} 的绑定目标父路径不存在：{target}"
            )
    return FrozenApplicationLinkRoute(
        route_id=route.route_id,
        environment=normalized_environment,
        application_methods=route.application_methods,
        category_code=route.category_code,
        integration_profile_id=profile.id,
        integration_profile_version=profile.version,
        integration_profile_checksum=profile.checksum,
        required_fields=route.required_fields,
        compiled_request_template=compiled_template,
        payload_bindings=route.payload_bindings,
        secret_bindings=profile.secret_bindings,
    )


def validate_catalog_application_link_plans(catalog: Any) -> None:
    route_ids = [
        route.route_id
        for product in catalog.products.values()
        for route in product.features.application_links
    ]
    if len(route_ids) != len(set(route_ids)):
        duplicate = next(route_id for route_id in route_ids if route_ids.count(route_id) > 1)
        raise ApplicationConfigurationError(f"申请链接 routeId 重复：{duplicate}")
    for product in catalog.products.values():
        for environment in product.environments:
            for method in product.applicationMethods:
                compile_application_link_plan(
                    catalog=catalog,
                    product_code=product.code,
                    environment=environment,
                    method_code=method.code,
                )


def _validate_binding_source(source: str, enabled_fields: set[str], route_id: str) -> None:
    if source in {"product", "environment", "category", "payload"}:
        return
    field_name = source.removeprefix("payload.") if source.startswith("payload.") else source
    if field_name not in enabled_fields:
        raise ApplicationConfigurationError(
            f"路由 {route_id} 的绑定来源未在当前产品/申请方式启用：{source}"
        )


def _deep_merge(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _deep_merge(current, value)
        else:
            target[key] = deepcopy(value)


def _path_exists(content: Mapping[str, Any], path: str) -> bool:
    current: Any = content
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False
        current = current[part]
    return True


def _path_parent_exists(content: Mapping[str, Any], path: str) -> bool:
    parts = [part for part in path.split(".") if part]
    if not parts:
        return False
    current: Any = content
    for part in parts[:-1]:
        if not isinstance(current, Mapping) or part not in current:
            return False
        current = current[part]
    return isinstance(current, Mapping)


def _paths_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(f"{right}.") or right.startswith(f"{left}.")
