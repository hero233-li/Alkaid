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

__all__ = (
    "ENDPOINT_SPECS",
    "FIXED_AUDIT",
    "FIXED_PROVIDER",
    "FLOW_PROVIDER",
    "LOGIN",
    "PRODUCT_CHECKS",
    "ROTATE_TOKEN",
    "SUBMIT_APPLICATION",
)
