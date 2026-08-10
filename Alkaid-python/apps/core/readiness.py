from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import connection

from apps.utils.application_links import (
    validate_catalog_application_link_plans,
)
from apps.utils.http.config import validate_cjdk_jyrc_readiness
from apps.utils.product_Conf.catalog import load_product_catalog
from apps.workflow.product_applications.common.agreement import validate_agreement_messages
from apps.workflow.product_applications.identity.gateway import validate_identity_messages


@dataclass(frozen=True)
class ReadinessReport:
    ready: bool
    checks: dict[str, Any]
    error: Exception | None = None


def collect_readiness() -> ReadinessReport:
    checks: dict[str, Any] = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"

        catalog = load_product_catalog()
        validate_catalog_application_link_plans(catalog)
        checks["catalog"] = {
            "status": "ok",
            "version": catalog.reference.version,
            "products": len(catalog.products),
        }
        checks["agreementMessages"] = {
            "status": "ok",
            **validate_agreement_messages(),
        }
        checks["identityMessages"] = {
            "status": "ok",
            **validate_identity_messages(),
        }
        environments = {
            environment
            for product in catalog.products.values()
            for environment in product.environments
        }
        validate_cjdk_jyrc_readiness(environments)
        checks["cjdkJyrc"] = "ok"
    except Exception as exc:
        checks["error"] = type(exc).__name__
        return ReadinessReport(ready=False, checks=checks, error=exc)
    return ReadinessReport(ready=True, checks=checks)
