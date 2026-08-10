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

from apps.utils.application_links import (  # noqa: E402
    compile_application_link_plan,
)
from apps.utils.product_Conf.catalog import load_product_catalog  # noqa: E402
from apps.workflow.product_applications.common.agreement import (  # noqa: E402
    validate_agreement_messages,
)
from apps.workflow.product_applications.identity.gateway import (  # noqa: E402
    validate_identity_messages,
)
from apps.workflow.product_applications.workflow_engine import (  # noqa: E402
    validate_product_workflow,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the unified product catalog")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compatibility flag; validation is always performed",
    )
    parser.parse_args()
    catalog = load_product_catalog()
    agreement_summary = validate_agreement_messages()
    identity_summary = validate_identity_messages()
    for product in catalog.products.values():
        validate_product_workflow(product.workflow)
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
        f"agreement_messages={agreement_summary['messages']}, "
        f"identity_messages={identity_summary['messages']}, "
        f"checksum={catalog.checksum}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
