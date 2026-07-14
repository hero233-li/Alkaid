import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from apps.integrations.mock_product.client import create_product_http_client


@override_settings(EXTERNAL_SYSTEM_MODE="real", MOCK_PRODUCT_BASE_URL="")
def test_real_mode_never_falls_back_to_mock_transport() -> None:
    with pytest.raises(ImproperlyConfigured, match="MOCK_PRODUCT_BASE_URL"):
        create_product_http_client("fixed-token")


def test_celery_autodiscovery_registers_product_data_tasks() -> None:
    from config.celery import app

    original_eager = app.conf.task_always_eager
    try:
        app.conf.task_always_eager = False
        app.loader.import_default_modules()
        expected = {
            "apps.product_data.verification_approval.tasks.execute_verification_approval",
            "apps.product_data.application_data.tasks.execute_application_data",
            "apps.product_data.card_status.tasks.execute_card_status",
            "apps.product_data.loan_status.tasks.execute_loan_status",
        }
        assert expected <= set(app.tasks)
    finally:
        app.conf.task_always_eager = original_eager
