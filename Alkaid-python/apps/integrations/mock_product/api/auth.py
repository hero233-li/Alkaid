from apps.integrations.contracts import AuthSpec, EndpointSpec, TokenSource, TokenUpdateSpec
from apps.integrations.mock_product.models import LoginResponse, OperationResponse

FLOW_PROVIDER = "product_flow"
FIXED_PROVIDER = "fixed_external"

LOGIN = EndpointSpec(
    operation_id="mock_product.login",
    method="POST",
    path="/auth/token",
    response_model=LoginResponse,
    token_update=TokenUpdateSpec(
        provider=FLOW_PROVIDER,
        source=TokenSource.RESPONSE_BODY,
        path="data.token",
    ),
)

ROTATE_TOKEN = EndpointSpec(
    operation_id="mock_product.rotate_token",
    method="POST",
    path="/auth/rotate",
    response_model=OperationResponse,
    auth=AuthSpec(provider=FLOW_PROVIDER),
    token_update=TokenUpdateSpec(
        provider=FLOW_PROVIDER,
        source=TokenSource.RESPONSE_HEADER,
        path="X-New-Token",
    ),
    success_path="code",
    success_values=("0000",),
)
