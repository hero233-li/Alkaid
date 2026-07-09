"""Compatibility package; product handlers moved to ``product_applications``."""

from apps.product_data.product_applications.handlers import get_product_handler

__all__ = ("get_product_handler",)
