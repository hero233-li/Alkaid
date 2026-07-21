"""Stable public facade for product catalog loading and models."""

from functools import lru_cache
from pathlib import Path

from apps.product_data.catalog_loader import read_product_catalog
from apps.product_data.catalog_models import (
    CatalogApplicationLinkRoute,
    CatalogApplicationMethod,
    CatalogFeatures,
    CatalogField,
    ProductCatalog,
    ProductCatalogError,
    ProductCatalogSource,
    ProductExecutionSnapshot,
    ProductReferenceData,
)
from apps.product_data.product_applications.schemas import ProductApplicationConfig

CONFIG_ROOT = Path(__file__).with_name("configs")
PRODUCT_ROOT = CONFIG_ROOT / "products"
REFERENCE_PATH = CONFIG_ROOT / "reference_data.json"


def load_product_catalog(
    product_root: Path | None = None,
    reference_path: Path | None = None,
) -> ProductCatalog:
    if product_root is None and reference_path is None:
        return _load_default_product_catalog()
    return read_product_catalog(product_root or PRODUCT_ROOT, reference_path or REFERENCE_PATH)


@lru_cache(maxsize=1)
def _load_default_product_catalog() -> ProductCatalog:
    return read_product_catalog(PRODUCT_ROOT, REFERENCE_PATH)


@lru_cache(maxsize=1)
def load_product_ui_config() -> ProductApplicationConfig:
    return load_product_catalog().to_ui_config()


def clear_product_catalog_cache() -> None:
    _load_default_product_catalog.cache_clear()
    load_product_ui_config.cache_clear()


__all__ = (
    "CatalogApplicationLinkRoute",
    "CatalogApplicationMethod",
    "CatalogFeatures",
    "CatalogField",
    "ProductCatalog",
    "ProductCatalogError",
    "ProductCatalogSource",
    "ProductExecutionSnapshot",
    "ProductReferenceData",
    "clear_product_catalog_cache",
    "load_product_catalog",
    "load_product_ui_config",
)
