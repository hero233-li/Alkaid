from apps.integrations.mock_product.api.application import PRODUCT_CHECKS, SUBMIT_APPLICATION
from apps.integrations.mock_product.api.audit import FIXED_AUDIT
from apps.integrations.mock_product.api.auth import (
    FIXED_PROVIDER,
    FLOW_PROVIDER,
    LOGIN,
    ROTATE_TOKEN,
)

ENDPOINT_SPECS = {
    endpoint.operation_id: endpoint
    for endpoint in (
        LOGIN,
        *PRODUCT_CHECKS.values(),
        ROTATE_TOKEN,
        SUBMIT_APPLICATION,
        FIXED_AUDIT,
    )
}


def validate_product_endpoint_coverage(product_codes: set[str]) -> None:
    configured = set(PRODUCT_CHECKS)
    missing = sorted(product_codes - configured)
    orphaned = sorted(configured - product_codes)
    problems: list[str] = []
    if missing:
        problems.append(f"缺少产品检查接口：{', '.join(missing)}")
    if orphaned:
        problems.append(f"存在无产品配置的检查接口：{', '.join(orphaned)}")
    if problems:
        raise ValueError("；".join(problems))


__all__ = (
    "ENDPOINT_SPECS",
    "FIXED_AUDIT",
    "FIXED_PROVIDER",
    "FLOW_PROVIDER",
    "LOGIN",
    "PRODUCT_CHECKS",
    "ROTATE_TOKEN",
    "SUBMIT_APPLICATION",
    "validate_product_endpoint_coverage",
)
