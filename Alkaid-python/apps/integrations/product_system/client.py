from django.conf import settings

from apps.integrations.application_link.mock_transport import create_application_link_mock_transport
from apps.integrations.business_access.mock_transport import create_business_access_mock_transport
from apps.integrations.http import HttpClient, HttpClientConfig
from apps.integrations.product_system.config import resolve_base_url, resolve_token
from apps.integrations.verification_approval.mock_transport import (
    create_verification_approval_mock_transport,
)

MOCK_TRANSPORTS = {
    "application_link": create_application_link_mock_transport,
    "business_access": create_business_access_mock_transport,
    "verification_approval": create_verification_approval_mock_transport,
}


def create_product_system_client(service: str, environment: str | None = None) -> HttpClient:
    if settings.EXTERNAL_SYSTEM_MODE == "mock":
        return HttpClient(
            HttpClientConfig(base_url=resolve_base_url(service, environment), max_retries=0),
            transport=MOCK_TRANSPORTS[service](),
        )
    return HttpClient(
        HttpClientConfig(
            base_url=resolve_base_url(service, environment),
            token=resolve_token(service),
            timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
            connect_timeout_seconds=settings.HTTP_CONNECT_TIMEOUT_SECONDS,
            write_timeout_seconds=settings.HTTP_WRITE_TIMEOUT_SECONDS,
            pool_timeout_seconds=settings.HTTP_POOL_TIMEOUT_SECONDS,
            max_retries=settings.HTTP_MAX_RETRIES,
            retry_backoff_seconds=settings.HTTP_RETRY_BACKOFF_SECONDS,
            retry_max_backoff_seconds=settings.HTTP_RETRY_MAX_BACKOFF_SECONDS,
        )
    )
