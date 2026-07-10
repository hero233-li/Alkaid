from apps.integrations.contracts import AuthSpec, EndpointSpec
from apps.integrations.mock_product.api.auth import FLOW_PROVIDER
from apps.integrations.mock_product.models import OperationResponse

PRODUCT_CHECKS = {
    "product-a": EndpointSpec(
        operation_id="mock_product.whitelist_check",
        method="POST",
        path="/checks/whitelist",
        response_model=OperationResponse,
        auth=AuthSpec(provider=FLOW_PROVIDER),
        success_path="code",
        success_values=("0000",),
    ),
    "product-b": EndpointSpec(
        operation_id="mock_product.red_shield_check",
        method="POST",
        path="/checks/red-shield",
        response_model=OperationResponse,
        auth=AuthSpec(provider=FLOW_PROVIDER),
        success_path="code",
        success_values=("0000",),
    ),
    "product-c": EndpointSpec(
        operation_id="mock_product.credit_check",
        method="POST",
        path="/checks/credit",
        response_model=OperationResponse,
        auth=AuthSpec(provider=FLOW_PROVIDER),
        success_path="code",
        success_values=("0000",),
    ),
}

SUBMIT_APPLICATION = EndpointSpec(
    operation_id="mock_product.submit_application",
    method="POST",
    path="/applications",
    response_model=OperationResponse,
    auth=AuthSpec(provider=FLOW_PROVIDER),
    success_path="code",
    success_values=("0000",),
)
