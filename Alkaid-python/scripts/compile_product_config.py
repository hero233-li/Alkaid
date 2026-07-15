#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

import django  # noqa: E402

django.setup()

from apps.integrations.mock_product.api import (  # noqa: E402
    validate_product_endpoint_coverage,
)
from apps.integrations.mock_product.messages import validate_message_catalog  # noqa: E402
from apps.product_data.catalog import load_product_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the unified product catalog")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compatibility flag; validation is always performed",
    )
    parser.parse_args()
    catalog = load_product_catalog()
    validate_product_endpoint_coverage(set(catalog.products))
    message_summary = validate_message_catalog()
    for product in catalog.products.values():
        for method in product.applicationMethods:
            catalog.snapshot(product.code, method.code)
    print(
        "Product catalog is valid: "
        f"version={catalog.reference.version}, "
        f"products={len(catalog.products)}, "
        f"raw_messages={message_summary['messages']}, "
        f"checksum={catalog.checksum}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
