from apps.integrations.contracts import AuthSpec, EndpointSpec, RetryMode
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
        retry_mode=RetryMode.SAFE,
    ),
    "product-b": EndpointSpec(
        operation_id="mock_product.red_shield_check",
        method="POST",
        path="/checks/red-shield",
        response_model=OperationResponse,
        auth=AuthSpec(provider=FLOW_PROVIDER),
        success_path="code",
        success_values=("0000",),
        retry_mode=RetryMode.SAFE,
    ),
    "product-c": EndpointSpec(
        operation_id="mock_product.credit_check",
        method="POST",
        path="/checks/credit",
        response_model=OperationResponse,
        auth=AuthSpec(provider=FLOW_PROVIDER),
        success_path="code",
        success_values=("0000",),
        retry_mode=RetryMode.SAFE,
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
