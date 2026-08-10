from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from copy import deepcopy
from time import monotonic
from typing import Any

from apps.utils.application_links import ApplicationConfigurationError
from apps.utils.http import config
from apps.utils.http.contracts import IntegrationObserver
from apps.utils.java.java_gateway import (
    JavaGateway,
    JavaGatewayConfig,
)
from apps.utils.product_Conf.catalog import FrozenApplicationLinkRoute

logger = logging.getLogger(__name__)
_MISSING = object()


def build_application_link_request(
    *,
    plan: FrozenApplicationLinkRoute,
    normalized_payload: dict[str, Any],
    secret_resolver: Any | None = None,
) -> dict[str, Any]:
    bound_payload = deepcopy(plan.compiled_request_template)
    missing = [field for field in plan.required_fields if _is_blank(normalized_payload.get(field))]
    if missing:
        raise ApplicationConfigurationError("申请链接缺少必填字段：" + ", ".join(sorted(missing)))
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
    for target, reference in plan.secret_bindings.items():
        try:
            if secret_resolver is None:
                secret_value = config.resolve_secret(reference)
            elif callable(secret_resolver):
                secret_value = secret_resolver(reference)
            else:
                secret_value = secret_resolver.resolve(reference)
        except (KeyError, ValueError) as exc:
            raise ApplicationConfigurationError(f"申请链接秘密配置不可用：{reference}") from exc
        if not secret_value:
            raise ApplicationConfigurationError(f"申请链接秘密配置为空：{reference}")
        _set_value(bound_payload, target, secret_value)
    project_id = normalized_payload.get("cooperationProjectId")
    request = {
        "env": plan.environment,
        "product": str(normalized_payload.get("product") or ""),
        "category": plan.category_code.display_name,
        "payload": bound_payload,
    }
    if project_id not in {None, ""}:
        request["cooperationProjectId"] = str(project_id).strip()
    return request


def generate_application_link(
    *,
    plan: FrozenApplicationLinkRoute,
    normalized_payload: Mapping[str, Any],
    observer: IntegrationObserver,
    trace_id: str,
) -> dict[str, str]:
    integration_settings = config.get_cjdk_jyrc_settings()
    java_request = build_application_link_request(
        plan=plan,
        normalized_payload=dict(normalized_payload),
    )
    call_path = (
        "mock://java-application-link"
        if integration_settings.mode == "mock"
        else integration_settings.java_gateway.main_class
    )
    handle = observer.request_started(
        step="application_link.generate_link",
        method="JAVA",
        url=call_path,
        headers={},
        body=java_request,
    )
    started_at = monotonic()
    logger.info(
        "application_link_java_started",
        extra={
            "trace_id": trace_id,
            "env": java_request["env"],
            "product": java_request["product"],
            "category": java_request["category"],
            "cooperation_project_id": java_request.get("cooperationProjectId"),
            "payload_fields": sorted(java_request["payload"]),
        },
    )
    try:
        raw = (
            _mock_java_result(java_request)
            if integration_settings.mode == "mock"
            else execute_java(java_request)
        )
        links = {
            "internal_url": _required_link(raw, "internal_url", "internalUrl"),
            "external_url": _required_link(raw, "external_url", "externalUrl"),
        }
    except Exception as exc:
        observer.request_finished(
            handle,
            status_code=None,
            headers={},
            body={},
            duration_ms=_duration_ms(started_at),
            error=exc,
        )
        raise
    observer.request_finished(
        handle,
        status_code=0,
        headers={},
        body=links,
        duration_ms=_duration_ms(started_at),
        error=None,
    )
    logger.info("application_link_java_completed", extra={"trace_id": trace_id})
    return links


def execute_java(java_request: dict[str, Any]) -> dict[str, Any]:
    settings = config.get_cjdk_jyrc_settings().java_gateway
    return JavaGateway(
        JavaGatewayConfig(
            sdk_dir=settings.sdk_dir,
            java_executable=settings.java_executable,
            jar=settings.jar,
            main_class=settings.main_class,
            output_encoding=settings.output_encoding,
            timeout_seconds=settings.timeout_seconds,
        )
    ).execute(java_request)


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
    raise ApplicationConfigurationError(f"申请链接绑定来源不存在：{source}")


def _get_value(content: Mapping[str, Any], path: str) -> Any:
    current: Any = content
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ApplicationConfigurationError(f"申请链接绑定来源不存在：payload.{path}")
        current = current[part]
    return current


def _set_value(content: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ApplicationConfigurationError("申请链接绑定目标路径不能为空")
    current = content
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            raise ApplicationConfigurationError(f"申请链接绑定目标不是 JSON 对象：{path}")
        current = child
    current[parts[-1]] = value


def _required_link(source: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    raise RuntimeError(f"Java 返回缺少申请链接：{'/'.join(keys)}")


def _mock_java_result(java_request: dict[str, Any]) -> dict[str, str]:
    digest = (
        hashlib.sha256(json.dumps(java_request, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        .hexdigest()[:12]
        .upper()
    )
    link_id = f"LINK-{digest}"
    return {
        "internal_url": f"https://cjdk-jyrc.mock/application-entry/{link_id}",
        "external_url": f"https://cjdk-jyrc.mock/application-entry/{link_id}?scope=external",
    }


def _duration_ms(started_at: float) -> int:
    return max(0, int((monotonic() - started_at) * 1000))


def _is_blank(value: Any) -> bool:
    return value is None or value == ""
