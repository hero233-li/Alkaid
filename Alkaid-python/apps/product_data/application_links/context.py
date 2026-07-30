from dataclasses import dataclass
from typing import Any

from apps.jobs.models import Job
from apps.product_data.application_links.schemas import (
    ApplicationLinkExecutionSnapshot,
    ApplicationLinkResult,
    ApplicationLinkSubmission,
)


@dataclass
class ApplicationLinkContext:
    """Data shared by the code-ordered application-link flow."""

    job: Job
    payload: dict[str, Any]
    submission: ApplicationLinkSubmission | None = None
    execution_snapshot: ApplicationLinkExecutionSnapshot | None = None
    result: ApplicationLinkResult | None = None
