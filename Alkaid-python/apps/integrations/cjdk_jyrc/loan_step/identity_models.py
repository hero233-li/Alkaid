from __future__ import annotations

from typing import Any

from pydantic import Field

from apps.integrations.cjdk_jyrc.models import CjdkResponseModel


class GenericIdentityBody(CjdkResponseModel):
    request: dict[str, Any] | None = None
    response: dict[str, Any] = Field(default_factory=dict)


class GenericIdentityEnvelope(CjdkResponseModel):
    rsp_body: GenericIdentityBody = Field(alias="RSP_BODY")
    rsp_head: dict[str, Any] = Field(default_factory=dict, alias="RSP_HEAD")
