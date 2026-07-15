from apps.integrations.contracts import AuthSpec, EndpointSpec
from apps.integrations.mock_product.api.auth import FIXED_PROVIDER
from apps.integrations.mock_product.models import OperationResponse

FIXED_AUDIT = EndpointSpec(
    operation_id="fixed_external.audit",
    method="POST",
    path="/fixed/audit",
    response_model=OperationResponse,
    auth=AuthSpec(provider=FIXED_PROVIDER, header="X-Api-Token", prefix=""),
    success_path="code",
    success_values=("0000",),
)
