"""Celery autodiscovery entrypoint for feature-local product-data tasks."""

from apps.product_data.application_links.tasks import execute_application_link
from apps.product_data.business_access.tasks import execute_business_access_task
from apps.product_data.product_applications.tasks import execute_product_application

__all__ = (
    "execute_application_link",
    "execute_business_access_task",
    "execute_product_application",
)
