"""Celery autodiscovery entrypoint for product application tasks."""

from apps.product_data.product_applications.tasks import execute_product_application

__all__ = ("execute_product_application",)
