from dataclasses import dataclass, field
from typing import Any

from apps.integrations.mock_product.models import OperationResponse, RequestHead
from apps.jobs.models import Job
from apps.product_data.catalog import ProductExecutionSnapshot
from apps.product_data.product_applications.schemas import ProductApplicationSubmission


@dataclass
class ProductApplicationContext:
    """Data shared by the code-ordered product-application flow."""

    job: Job
    submission: ProductApplicationSubmission | None = None
    execution_snapshot: ProductExecutionSnapshot | None = None
    request_head: RequestHead | None = None
    application_response: OperationResponse | None = None
    flow_token_versions: dict[str, int] = field(default_factory=dict)
    result: dict[str, Any] | None = None
