import hashlib
import json
from pathlib import Path
from typing import Any

from apps.core.errors import ConfigurationError
from apps.product_data.catalog_models import (
    ProductCatalog,
    ProductCatalogError,
    ProductCatalogSource,
    ProductReferenceData,
)
from apps.product_data.catalog_validation import validate_catalog_environments


def read_product_catalog(product_root: Path, reference_path: Path) -> ProductCatalog:
    try:
        reference_raw = _read_json(reference_path)
        reference = ProductReferenceData.model_validate(reference_raw)
        products: dict[str, ProductCatalogSource] = {}
        product_raw: dict[str, Any] = {}
        for path in sorted(product_root.glob("*.json")):
            raw = _read_json(path)
            product = ProductCatalogSource.model_validate(raw)
            if product.code in products:
                raise ProductCatalogError(f"产品代码重复：{product.code}")
            products[product.code] = product
            product_raw[product.code] = raw
        if not products:
            raise ProductCatalogError("没有找到产品配置")
        validate_catalog_environments(reference, products)
        checksum = _checksum({"reference": reference_raw, "products": product_raw})
        catalog = ProductCatalog(reference=reference, products=products, checksum=checksum)
        catalog.to_ui_config()
        return catalog
    except ProductCatalogError:
        raise
    except (OSError, ValueError, ConfigurationError) as exc:
        raise ProductCatalogError(f"产品目录配置无效：{exc}") from exc


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _checksum(content: dict[str, Any]) -> str:
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
