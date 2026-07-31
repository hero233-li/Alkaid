import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from apps.integrations.mock_product.client import create_product_http_client


@override_settings(EXTERNAL_SYSTEM_MODE="real", MOCK_PRODUCT_BASE_URL="")
def test_real_mode_never_falls_back_to_mock_transport() -> None:
    with pytest.raises(ImproperlyConfigured, match="MOCK_PRODUCT_BASE_URL"):
        create_product_http_client("fixed-token")


def test_celery_autodiscovery_registers_product_application_task() -> None:
    from config.celery import app

    original_eager = app.conf.task_always_eager
    try:
        app.conf.task_always_eager = False
        app.loader.import_default_modules()
        assert "apps.product_data.tasks.execute_product_application" in app.tasks
    finally:
        app.conf.task_always_eager = original_eager


def test_product_application_compatibility_modules_remain_importable() -> None:
    import apps.integrations.mock_product as mock_product
    import apps.product_data.tasks as product_data_tasks

    assert mock_product.__name__ == "apps.integrations.mock_product"
    assert (
        product_data_tasks.execute_product_application.name
        == "apps.product_data.tasks.execute_product_application"
    )
