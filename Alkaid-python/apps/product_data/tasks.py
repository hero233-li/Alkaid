"""Celery autodiscovery entrypoint for feature-local product-data tasks."""

from apps.product_data.application_data.tasks import execute_application_data_task
from apps.product_data.application_links.tasks import execute_application_link
from apps.product_data.business_access.tasks import execute_business_access_task
from apps.product_data.card_status.tasks import execute_card_status_task
from apps.product_data.loan_status.tasks import execute_loan_status_task
from apps.product_data.product_applications.tasks import execute_product_application
from apps.product_data.verification_approval.tasks import execute_verification_approval_task

__all__ = (
    "execute_application_link",
    "execute_business_access_task",
    "execute_product_application",
    "execute_verification_approval_task",
    "execute_application_data_task",
    "execute_card_status_task",
    "execute_loan_status_task",
)
