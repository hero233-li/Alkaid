from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Protocol

from apps.integrations.cjdk_jyrc.models import GenerateApplicationLinkRequest
from apps.product_data.product_applications.contracts import FrozenApplicationLinkRoute

_MISSING = object()


class ApplicationLinkRequestError(ValueError):
    pass


class SecretResolver(Protocol):
    def resolve(self, reference: str) -> str: ...


class ConfigSecretResolver:
    def resolve(self, reference: str) -> str:
        from apps.integrations.cjdk_jyrc.config import resolve_secret

        return resolve_secret(reference)


def build_application_link_request(
    *,
    plan: FrozenApplicationLinkRoute,
    normalized_payload: dict[str, Any],
    secret_resolver: SecretResolver | None = None,
) -> GenerateApplicationLinkRequest:
    bound_payload = deepcopy(plan.compiled_request_template)

    missing = [field for field in plan.required_fields if _is_blank(normalized_payload.get(field))]
    if missing:
        raise ApplicationLinkRequestError("申请链接缺少必填字段：" + ", ".join(sorted(missing)))

    for target, source in plan.payload_bindings.items():
        value = _runtime_value(
            source,
            product=normalized_payload.get("product"),
            environment=plan.environment,
            category=plan.category_code.display_name,
            normalized_payload=normalized_payload,
        )
        if value is _MISSING:
            continue
        _set_value(bound_payload, target, deepcopy(value))

    resolver = secret_resolver or ConfigSecretResolver()
    for target, reference in plan.secret_bindings.items():
        try:
            secret_value = resolver.resolve(reference)
        except (KeyError, ValueError) as exc:
            raise ApplicationLinkRequestError(f"申请链接秘密配置不可用：{reference}") from exc
        if not secret_value:
            raise ApplicationLinkRequestError(f"申请链接秘密配置为空：{reference}")
        _set_value(bound_payload, target, secret_value)

    project_id = normalized_payload.get("cooperationProjectId")
    return GenerateApplicationLinkRequest(
        env=plan.environment,
        product=str(normalized_payload.get("product") or ""),
        category=plan.category_code.display_name,
        cooperationProjectId=str(project_id).strip() if project_id not in {None, ""} else None,
        payload=bound_payload,
    )


def _runtime_value(
    source: str,
    *,
    product: object,
    environment: str,
    category: str,
    normalized_payload: dict[str, Any],
) -> Any:
    if source == "product":
        return product
    if source == "environment":
        return environment
    if source == "category":
        return category
    if source == "payload":
        return normalized_payload
    if source.startswith("payload."):
        return _get_value(normalized_payload, source.removeprefix("payload."))
    if source in normalized_payload:
        return normalized_payload[source]
    raise ApplicationLinkRequestError(f"申请链接绑定来源不存在：{source}")


def _get_value(content: Mapping[str, Any], path: str) -> Any:
    current: Any = content
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ApplicationLinkRequestError(f"申请链接绑定来源不存在：payload.{path}")
        current = current[part]
    return current


def _set_value(content: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ApplicationLinkRequestError("申请链接绑定目标路径不能为空")
    current = content
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            raise ApplicationLinkRequestError(f"申请链接绑定目标不是 JSON 对象：{path}")
        current = child
    current[parts[-1]] = value


def _is_blank(value: Any) -> bool:
    return value is None or value == ""
