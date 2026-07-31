from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from apps.integrations.cjdk_jyrc.models import (
    GenerateApplicationLinkRequest,
)
from apps.product_data.catalog import PRODUCT_ROOT

_MISSING = object()


class ApplicationLinkRequestError(ValueError):
    pass


def build_application_link_request(
    *,
    product: str,
    environment: str,
    category: str,
    submission_payload: dict[str, Any],
    product_root: Path = PRODUCT_ROOT,
) -> GenerateApplicationLinkRequest:
    route = _find_route(product, environment, product_root)
    configured_category = str(route.get("category") or "").strip()
    if configured_category != category:
        raise ApplicationLinkRequestError(
            f"产品 {product} 在环境 {environment} 的申请链接类别不一致"
        )

    _validate_required_fields(
        route,
        product=product,
        environment=environment,
        category=category,
        submission_payload=submission_payload,
    )

    template = route.get("payload")
    if not isinstance(template, Mapping):
        raise ApplicationLinkRequestError(
            f"产品 {product} 在环境 {environment} "
            "缺少 applicationLinks.payload"
        )
    bound_payload = deepcopy(dict(template))

    bindings = route.get("payloadBindings") or {}
    if not isinstance(bindings, Mapping):
        raise ApplicationLinkRequestError(
            "payloadBindings 必须是 JSON 对象"
        )

    for raw_target, raw_source in bindings.items():
        target = str(raw_target).strip()
        source = str(raw_source).strip()
        if not target or not source:
            raise ApplicationLinkRequestError(
                "payloadBindings 的目标和来源不能为空"
            )

        value = _runtime_value(
            source,
            product=product,
            environment=environment,
            category=category,
            submission_payload=submission_payload,
        )
        if value is _MISSING:
            continue

        _set_value(
            bound_payload,
            target,
            deepcopy(value),
        )

    project_id = submission_payload.get("cooperationProjectId")
    if project_id in {None, ""}:
        project_id = submission_payload.get("projectId")

    return GenerateApplicationLinkRequest(
        env=environment.strip().upper(),
        product=product,
        category=category,
        cooperationProjectId=(
            str(project_id).strip()
            if project_id not in {None, ""}
            else None
        ),
        payload=bound_payload,
    )


def _find_route(
    product: str,
    environment: str,
    product_root: Path,
) -> dict[str, Any]:
    normalized_environment = environment.strip().upper()

    for path in sorted(product_root.glob("*.json")):
        try:
            source = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ApplicationLinkRequestError(
                f"产品配置读取失败：{path.name}: {exc}"
            ) from exc

        if source.get("code") != product:
            continue

        routes = (
            (source.get("features") or {})
            .get("applicationLinks")
            or []
        )
        if not isinstance(routes, list):
            raise ApplicationLinkRequestError(
                "features.applicationLinks 必须是数组"
            )

        for route in routes:
            if not isinstance(route, dict):
                raise ApplicationLinkRequestError(
                    "applicationLinks 项必须是 JSON 对象"
                )

            route_environment = str(
                route.get("environment") or ""
            ).strip().upper()
            if route_environment == normalized_environment:
                return route

        raise ApplicationLinkRequestError(
            f"产品 {product} 在环境 "
            f"{normalized_environment} 未配置申请链接"
        )

    raise ApplicationLinkRequestError(f"未知产品：{product}")


def _validate_required_fields(
    route: Mapping[str, Any],
    *,
    product: str,
    environment: str,
    category: str,
    submission_payload: dict[str, Any],
) -> None:
    required = route.get("requiredFields") or []
    if not isinstance(required, list):
        raise ApplicationLinkRequestError(
            "requiredFields 必须是数组"
        )

    missing: list[str] = []
    for raw_source in required:
        source = str(raw_source).strip()
        if not source:
            continue

        value = _runtime_value(
            source,
            product=product,
            environment=environment,
            category=category,
            submission_payload=submission_payload,
        )
        if value is _MISSING or value is None or value == "":
            missing.append(source)

    if missing:
        raise ApplicationLinkRequestError(
            "申请链接缺少必填字段："
            + ", ".join(sorted(missing))
        )


def _runtime_value(
    source: str,
    *,
    product: str,
    environment: str,
    category: str,
    submission_payload: dict[str, Any],
) -> Any:
    if source == "product":
        return product
    if source == "environment":
        return environment.strip().upper()
    if source == "category":
        return category

    if source in {"cooperationProjectId", "projectId"}:
        value = submission_payload.get("cooperationProjectId")
        if value in {None, ""}:
            value = submission_payload.get("projectId")
        return _MISSING if value in {None, ""} else value

    if source == "payload":
        return submission_payload

    if source.startswith("payload."):
        return _get_value(
            submission_payload,
            source.removeprefix("payload."),
        )

    if source in submission_payload:
        return submission_payload[source]

    raise ApplicationLinkRequestError(
        f"申请链接绑定来源不存在：{source}"
    )


def _get_value(
    content: Mapping[str, Any],
    path: str,
) -> Any:
    current: Any = content

    for part in path.split("."):
        if (
            not isinstance(current, Mapping)
            or part not in current
        ):
            raise ApplicationLinkRequestError(
                f"申请链接绑定来源不存在：payload.{path}"
            )
        current = current[part]

    return current


def _set_value(
    content: dict[str, Any],
    path: str,
    value: Any,
) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ApplicationLinkRequestError(
            "申请链接绑定目标路径不能为空"
        )

    current = content
    for part in parts[:-1]:
        child = current.get(part)

        if child is None:
            child = {}
            current[part] = child

        if not isinstance(child, dict):
            raise ApplicationLinkRequestError(
                f"申请链接绑定目标不是 JSON 对象：{path}"
            )

        current = child

    current[parts[-1]] = value
