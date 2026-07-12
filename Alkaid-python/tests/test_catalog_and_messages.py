import json

import pytest

from apps.integrations.mock_product import messages
from apps.integrations.mock_product.api import validate_product_endpoint_coverage
from apps.product_data.catalog import (
    clear_product_catalog_cache,
    load_product_catalog,
    load_product_ui_config,
)


def test_catalog_is_cached_and_derives_execution_and_ui_views() -> None:
    clear_product_catalog_cache()
    catalog = load_product_catalog()

    assert load_product_catalog() is catalog
    assert set(catalog.products) == {"product-a", "product-b", "product-c"}
    assert catalog.snapshot("product-a", "dynamic").required_fields
    assert {product.value for product in load_product_ui_config().products} == set(catalog.products)
    validate_product_endpoint_coverage(set(catalog.products))


def test_product_endpoint_coverage_rejects_missing_or_orphaned_products() -> None:
    with pytest.raises(ValueError, match="缺少产品检查接口"):
        validate_product_endpoint_coverage({"product-a", "new-product"})


def test_raw_message_returns_an_isolated_copy_and_catalog_is_valid() -> None:
    first = messages.new_message("application", "product_apply_v1")
    first["REQ_BODY"]["request"]["custNme"] = "changed"

    second = messages.new_message("application", "product_apply_v1")
    assert second["REQ_BODY"]["request"]["custNme"] == ""
    assert messages.validate_message_catalog() == {"groups": 1, "messages": 1}


def test_raw_message_validation_scans_templates_not_used_by_code(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "unused.json").write_text(
        json.dumps({"broken": {"REQ_BODY": {}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(messages, "MESSAGE_ROOT", tmp_path)
    messages.clear_message_cache()

    with pytest.raises(messages.ExternalMessageConfigurationError, match="REQ_HEAD"):
        messages.validate_message_catalog()

    messages.clear_message_cache()
