from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from apps.integrations.auth import TokenManager
from apps.integrations.contracts import BusinessResponseError, EndpointSpec, ResponseModel
from apps.integrations.http import HttpCallObserver, HttpClient


class EndpointExecutor:
    def __init__(self, client: HttpClient, tokens: TokenManager) -> None:
        self.client = client
        self.tokens = tokens

    def execute(
        self,
        endpoint: EndpointSpec[ResponseModel],
        *,
        body: BaseModel | None = None,
        form_data: Mapping[str, Any] | None = None,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        trace_id: str,
        observer: HttpCallObserver | None = None,
    ) -> ResponseModel:
        request_headers = dict(headers or {})
        request_headers.update(self.tokens.build_headers(endpoint.auth))
        result = self.client.request_detailed(
            endpoint.method,
            endpoint.path,
            response_model=endpoint.response_model,
            body=body,
            form_data=form_data,
            params=params,
            headers=request_headers,
            workflow_id=trace_id,
            observer=observer,
            response_validator=lambda response: self._validate_business_response(
                endpoint,
                response,
            ),
        )
        self.tokens.apply_update(endpoint.token_update, result)
        return result.data

    @staticmethod
    def _validate_business_response(
        endpoint: EndpointSpec[ResponseModel],
        response: ResponseModel,
    ) -> None:
        if endpoint.success_path is None:
            return
        value = response.model_dump(mode="json")
        for segment in endpoint.success_path.split("."):
            if not isinstance(value, dict) or segment not in value:
                raise BusinessResponseError(
                    f"{endpoint.operation_id} 响应缺少业务状态字段 {endpoint.success_path}"
                )
            value = value[segment]
        if value not in endpoint.success_values:
            raise BusinessResponseError(
                f"{endpoint.operation_id} 业务处理失败：{endpoint.success_path}={value!r}"
            )
