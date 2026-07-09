"""Celery autodiscovery entrypoint for feature-local product-data tasks."""

from apps.product_data.application_links.tasks import execute_application_link
from apps.product_data.product_applications.tasks import execute_product_application

__all__ = ("execute_application_link", "execute_product_application")
