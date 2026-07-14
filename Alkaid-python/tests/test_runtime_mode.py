import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from apps.integrations.application_link.adapter import ApplicationLinkAdapter, _configured_sign
from apps.integrations.mock_product.client import create_product_http_client
from apps.jobs.services import create_job


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


@pytest.mark.django_db
@override_settings(
    EXTERNAL_SYSTEM_MODE="real",
    APPLICATION_LINK_PROTOCOL_CONFIRMED=False,
)
def test_application_link_real_mode_requires_confirmed_protocol() -> None:
    job = create_job(
        kind="application_link_generation",
        name="protocol-gate",
        product="product-a",
        payload={},
        trace_id="protocol-gate",
        idempotency_key="protocol-gate",
        timeout_seconds=60,
    ).job
    with pytest.raises(ImproperlyConfigured, match="真实协议尚未确认"):
        with ApplicationLinkAdapter(job):
            pass


@override_settings(EXTERNAL_SYSTEM_MODE="real", APPLICATION_LINK_SIGNER="")
def test_application_link_real_mode_requires_signer() -> None:
    with pytest.raises(ImproperlyConfigured, match="APPLICATION_LINK_SIGNER"):
        _configured_sign("message")
