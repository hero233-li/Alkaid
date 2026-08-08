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

from apps.product_applications.cjdk.runtime import (  # noqa: E402
    compile_application_link_plan,
    validate_message_catalog,
)
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
    message_summary = validate_message_catalog()
    for product in catalog.products.values():
        for environment in product.environments:
            for method in product.applicationMethods:
                compile_application_link_plan(
                    catalog=catalog,
                    product_code=product.code,
                    environment=environment,
                    method_code=method.code,
                )
    print(
        "Product catalog is valid: "
        f"version={catalog.reference.version}, "
        f"products={len(catalog.products)}, "
        f"agreement_messages={message_summary['messages']}, "
        f"checksum={catalog.checksum}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
