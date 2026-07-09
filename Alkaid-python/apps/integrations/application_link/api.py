from apps.integrations.application_link.models import (
    CreateApplicationEnvelope,
    GenerateLinksEnvelope,
)
from apps.integrations.contracts import EndpointSpec

CREATE_APPLICATION = EndpointSpec(
    operation_id="application_link.create_application",
    method="POST",
    path="/applications",
    response_model=CreateApplicationEnvelope,
    success_path="code",
    success_values=("0000",),
)

CREATE_SUN_CODE_LINKS = EndpointSpec(
    operation_id="application_link.create_sun_code_links",
    method="POST",
    path="/links/sun-code",
    response_model=GenerateLinksEnvelope,
    success_path="code",
    success_values=("0000",),
)

CREATE_DYNAMIC_LINKS = EndpointSpec(
    operation_id="application_link.create_dynamic_links",
    method="POST",
    path="/links/dynamic",
    response_model=GenerateLinksEnvelope,
    success_path="code",
    success_values=("0000",),
)
