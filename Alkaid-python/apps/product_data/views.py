"""Compatibility imports for the moved product-application HTTP module."""

from apps.product_data.product_applications.views import (
    create_product_application,
    product_application_config,
)

__all__ = ("create_product_application", "product_application_config")
