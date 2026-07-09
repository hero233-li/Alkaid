import json

import pytest

from apps.product_data.execution_config import (
    ExecutionConfigurationError,
    ProductExecutionSnapshot,
    compile_execution_catalog,
    load_execution_catalog,
)


def test_source_config_compiles_to_current_runtime_catalog():
    source_catalog = compile_execution_catalog()
    runtime_catalog = load_execution_catalog()

    assert runtime_catalog == source_catalog
    assert runtime_catalog.version == 5
    assert set(runtime_catalog.products) == {"product-a", "product-b", "product-c"}
    assert runtime_catalog.products["product-a"].handler == "whitelist_application_v1"
    assert runtime_catalog.products["product-b"].handler == "red_shield_application_v1"
    assert runtime_catalog.products["product-c"].handler == "credit_application_v1"


def test_dynamic_application_snapshot_expands_and_requires_dynamic_fields():
    snapshot = load_execution_catalog().snapshot("product-a", "dynamic")

    assert snapshot.operation == "mock_product.product_a.dynamic_apply"
    assert snapshot.product_type == "whitelist_product"
    assert snapshot.handler == "whitelist_application_v1"
    assert snapshot.switch_payload_field == "whitelistEnabled"
    assert snapshot.fields == (
        "customer_name",
        "certificate_no",
        "phone",
        "customer_type",
        "organization_code",
        "outlet_code",
        "whitelist_enabled",
        "red_shield_enabled",
        "dynamic_term",
        "dynamic_amount",
    )
    assert "dynamic_term" in snapshot.required_fields
    assert "dynamic_amount" in snapshot.required_fields


def test_runtime_catalog_rejects_tampered_checksum(tmp_path):
    content = load_execution_catalog().model_dump(mode="json")
    content["products"]["product-a"]["name"] = "被篡改"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ExecutionConfigurationError, match="checksum"):
        load_execution_catalog(path)


def test_legacy_job_snapshot_is_mapped_to_a_versioned_handler():
    current = load_execution_catalog().snapshot("product-a").model_dump(mode="json")
    current.pop("handler")
    current.pop("product_type")
    current.pop("required_fields")
    current["field_definitions"] = {
        "customer_name": {
            "source": "application.personName",
            "target": "customer.name",
            "required": True,
            "transformer": "strip",
        }
    }

    restored = ProductExecutionSnapshot.model_validate(current)

    assert restored.handler == "whitelist_application_v1"
    assert restored.product_type == "legacy"
    assert restored.required_fields == ("customer_name",)
    assert restored.field_definitions["customer_name"].normalizer == "strip"


def test_product_types_select_handlers_without_workflow_configuration():
    catalog = load_execution_catalog()

    assert catalog.snapshot("product-a").handler == "whitelist_application_v1"
    assert catalog.snapshot("product-b").handler == "red_shield_application_v1"
    assert catalog.snapshot("product-c").handler == "credit_application_v1"
