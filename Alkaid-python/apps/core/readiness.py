from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import connection

from apps.integrations.cjdk_jyrc.config import validate_cjdk_jyrc_readiness
from apps.integrations.cjdk_jyrc.messages import (
    validate_message_catalog as validate_agreement_message_catalog,
)
from apps.product_data.catalog import load_product_catalog


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
        checks["catalog"] = {
            "status": "ok",
            "version": catalog.reference.version,
            "products": len(catalog.products),
        }
        checks["agreementMessages"] = {
            "status": "ok",
            **validate_agreement_message_catalog(),
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
