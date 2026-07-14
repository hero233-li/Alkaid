from apps.integrations.application_link.models import GenerateApplicationLinkEnvelope
from apps.integrations.contracts import EndpointSpec

CREATE_SUN_CODE_LINK = EndpointSpec(
    operation_id="application_link.generate_sun_code_link",
    method="POST",
    path="/links/sun-code",
    response_model=GenerateApplicationLinkEnvelope,
    success_path="code",
    success_values=("0000",),
)

CREATE_DYNAMIC_LINK = EndpointSpec(
    operation_id="application_link.generate_dynamic_link",
    method="POST",
    path="/links/dynamic",
    response_model=GenerateApplicationLinkEnvelope,
    success_path="code",
    success_values=("0000",),
)
