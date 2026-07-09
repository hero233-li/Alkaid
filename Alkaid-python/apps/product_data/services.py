"""Compatibility exports for the moved product-application service layer."""

from apps.product_data.product_applications.config import (
    CONFIG_PATH,
    ProductConfigurationError,
    load_product_application_config,
)
from apps.product_data.product_applications.services import (
    ProductApplicationExecutor,
    validate_customer_type,
    validate_submission,
)

__all__ = (
    "CONFIG_PATH",
    "ProductApplicationExecutor",
    "ProductConfigurationError",
    "load_product_application_config",
    "validate_customer_type",
    "validate_submission",
)
