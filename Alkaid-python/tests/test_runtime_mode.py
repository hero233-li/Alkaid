import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from apps.integrations.mock_product.client import create_product_http_client


@override_settings(EXTERNAL_SYSTEM_MODE="real", MOCK_PRODUCT_BASE_URL="")
def test_real_mode_never_falls_back_to_mock_transport() -> None:
    with pytest.raises(ImproperlyConfigured, match="MOCK_PRODUCT_BASE_URL"):
        create_product_http_client("fixed-token")
