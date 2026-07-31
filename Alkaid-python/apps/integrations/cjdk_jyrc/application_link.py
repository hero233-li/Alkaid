"""Application-link integration used only by the product-application flow."""

from __future__ import annotations

from apps.integrations.cjdk_jyrc.java_gateway import JavaApplicationLinkGateway
from apps.integrations.cjdk_jyrc.models import (
    ApplicationLinks,
    GenerateApplicationLinkRequest,
)
from apps.jobs.models import Job


class CjdkJyrcApplicationLinkAdapter:
    """Translate the product flow request into the local Java SDK call."""

    def __init__(self, job: Job) -> None:
        self.job = job
        self._gateway = JavaApplicationLinkGateway(job)

    def __enter__(self) -> "CjdkJyrcApplicationLinkAdapter":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def generate_link(
        self,
        request: GenerateApplicationLinkRequest,
    ) -> ApplicationLinks:
        return self._gateway.generate_link(request)
