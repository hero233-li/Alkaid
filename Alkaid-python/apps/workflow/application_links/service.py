from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.utils import timezone

from apps.utils.application_links import (
    ApplicationConfigurationError,
    compile_application_link_plan,
)
from apps.utils.http.contracts import IntegrationObserver
from apps.utils.java.application_link import generate_application_link
from apps.utils.product_Conf.catalog import (
    ApplicationLinkCategory,
    ProductCatalog,
    load_product_catalog,
)

from .schemas import (
    ApplicationLinkExecutionSnapshot,
    ApplicationLinkSubmission,
    LinkCategory,
)


class ApplicationLinkConfigurationError(ValueError):
    pass


_CATEGORY_CODES = {
    LinkCategory.SUN_CODE: ApplicationLinkCategory.SUN_CODE,
    LinkCategory.DYNAMIC_LINK: ApplicationLinkCategory.DYNAMIC_LINK,
}


def get_application_link_config() -> dict[str, Any]:
    catalog = load_product_catalog()
    project_ids = tuple(
        dict.fromkeys(
            product.cooperationProjectId
            for product in catalog.products.values()
            if product.cooperationProjectId
        )
    )
    return {
        "environments": [
            option.model_dump(mode="json") for option in catalog.reference.environments
        ],
        "products": [
            {
                "label": product.name,
                "value": product.code,
                "routes": [
                    {
                        "environment": route.environment,
                        "category": route.category_code.display_name,
                        "requiredFields": list(route.required_fields),
                    }
                    for route in product.features.application_links
                ],
            }
            for product in catalog.products.values()
            if product.features.application_links
        ],
        "cooperationProjects": [
            {"label": project_id, "value": project_id} for project_id in project_ids
        ],
    }


def resolve_execution_snapshot(
    submission: ApplicationLinkSubmission,
) -> tuple[ApplicationLinkSubmission, ApplicationLinkExecutionSnapshot]:
    catalog = load_product_catalog()
    product = catalog.product(submission.product)
    environment = _normalize_environment(catalog, submission.environment)
    category_code = _CATEGORY_CODES[submission.category]
    cooperation_project_id = _normalize_cooperation_project(
        catalog,
        submission.cooperation_project_id,
    )
    normalized = submission.model_copy(
        update={
            "product": product.code,
            "environment": environment,
            "cooperation_project_id": cooperation_project_id,
        }
    )
    normalized_payload = _normalized_payload(normalized)
    try:
        route = compile_application_link_plan(
            catalog=catalog,
            product_code=product.code,
            environment=environment,
            method_code=product.defaultApplicationMethod,
            category_code=category_code,
        )
    except ApplicationConfigurationError as exc:
        raise ApplicationLinkConfigurationError(str(exc)) from exc
    snapshot = ApplicationLinkExecutionSnapshot(
        catalog_version=catalog.reference.version,
        catalog_checksum=catalog.checksum,
        product_code=product.code,
        environment=environment,
        category=normalized.category,
        normalized_payload=normalized_payload,
        route=route,
    )
    return normalized, snapshot


def execute_application_link(
    *,
    snapshot: ApplicationLinkExecutionSnapshot,
    observer: IntegrationObserver,
    trace_id: str,
) -> dict[str, Any]:
    links = generate_application_link(
        plan=snapshot.route,
        normalized_payload=snapshot.normalized_payload,
        observer=observer,
        trace_id=trace_id,
    )
    return {
        "links": {
            "internalUrl": links["internal_url"],
            "externalUrl": links["external_url"],
            "generatedAt": timezone.now().isoformat(),
        }
    }


def submission_payload(submission: ApplicationLinkSubmission) -> dict[str, Any]:
    return submission.model_dump(mode="json", by_alias=True, exclude_none=True)


def _normalize_environment(catalog: ProductCatalog, value: str) -> str:
    normalized = value.strip().upper()
    for option in catalog.reference.environments:
        if normalized in {option.value.upper(), option.label.upper()}:
            return option.value
    raise ApplicationLinkConfigurationError(f"未知环境：{value}")


def _normalize_cooperation_project(
    catalog: ProductCatalog,
    value: str | None,
) -> str | None:
    normalized = (value or "").strip()
    known = {
        product.cooperationProjectId
        for product in catalog.products.values()
        if product.cooperationProjectId
    }
    if not normalized:
        return None
    if normalized not in known:
        raise ApplicationLinkConfigurationError("请选择有效的合作项目")
    return normalized


def _normalized_payload(submission: ApplicationLinkSubmission) -> dict[str, Any]:
    payload = dict(submission.payload)
    authoritative: Mapping[str, Any] = {
        "product": submission.product,
        "environment": submission.environment,
        "category": submission.category.value,
        "cooperationProjectId": submission.cooperation_project_id,
    }
    conflicts = [
        name
        for name, expected in authoritative.items()
        if name in payload and payload[name] != expected
    ]
    if conflicts:
        raise ApplicationLinkConfigurationError(
            "payload 与外层权威字段冲突：" + ", ".join(sorted(conflicts))
        )
    payload.update(
        {
            "product": submission.product,
            "environment": submission.environment,
            "category": submission.category.value,
        }
    )
    if submission.cooperation_project_id:
        payload["cooperationProjectId"] = submission.cooperation_project_id
    return payload
