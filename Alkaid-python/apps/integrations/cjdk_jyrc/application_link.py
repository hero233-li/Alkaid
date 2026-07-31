"""Application-link adapter for the product flow."""

from __future__ import annotations

from typing import Any

from apps.integrations.cjdk_jyrc.java_gateway import (
    JavaApplicationLinkGateway,
)
from apps.integrations.cjdk_jyrc.models import ApplicationLinks
from apps.integrations.cjdk_jyrc.request_builder import (
    build_application_link_request,
)
from apps.jobs.models import Job


class CjdkJyrcApplicationLinkAdapter:
    """Build the product-local payload and invoke JavaGateway."""

    def __init__(
        self,
        job: Job,
        environment: str,
    ) -> None:
        self.job = job
        self.environment = environment
        self._gateway = JavaApplicationLinkGateway(job)

    def __enter__(
        self,
    ) -> "CjdkJyrcApplicationLinkAdapter":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def generate_link(
        self,
        *,
        product: str,
        category: str,
        payload: dict[str, Any],
    ) -> ApplicationLinks:
        request = build_application_link_request(
            product=product,
            environment=self.environment,
            category=category,
            submission_payload=payload,
        )
        return self._gateway.generate_link(request)
