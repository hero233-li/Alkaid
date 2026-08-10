from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from enum import Enum
from typing import Any
from urllib.parse import parse_qs, quote, urljoin, urlsplit

import httpx
from django.conf import settings as django_settings
from django.utils import timezone
from pydantic import BaseModel, ConfigDict

from apps.utils.http import config
from apps.utils.http.client import HttpClient, HttpClientConfig
from apps.utils.http.config import EnvironmentSettings
from apps.utils.http.contracts import (
    BusinessResponseError,
    EndpointSpec,
    IntegrationObserver,
    ResponseModel,
)
from apps.workflow.product_applications.cjdk.mock import create_mock_transport


class SessionStatus(str, Enum):
    NOT_ESTABLISHED = "not_established"
    ESTABLISHED = "established"
    FAILED = "failed"


class SessionState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SessionStatus = SessionStatus.NOT_ESTABLISHED
    cookie_names: tuple[str, ...] = ()
    header_names: tuple[str, ...] = ()
    final_url: str | None = None


def may_forward_session_headers(url: str, policy: EnvironmentSettings) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host in {item.lower().rstrip(".") for item in policy.forward_session_headers_to_hosts}


def validate_cjdk_business_response(response_body: Any) -> None:
    if not isinstance(response_body, Mapping):
        return
    state = response_body.get("biz_state", response_body.get("bizState"))
    if str(state or "").strip().upper() not in {"F", "FAIL", "FAILED"}:
        return
    code = response_body.get("rsp_code", response_body.get("rspCode"))
    message = response_body.get("rsp_msg", response_body.get("rspMsg"))
    raise BusinessResponseError(
        f"CJDK-JYRC 业务处理失败：biz_state={state!r}；rsp_code={code!r}；rsp_msg={message!r}"
    )


SESSION_RESPONSE_HEADERS = ("X-Sd", "X-Token", "X-FCOS-SESSIONID")
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def evaluate_session_state(
    *,
    page_opened: bool,
    cookie_names: tuple[str, ...],
    header_names: tuple[str, ...],
    requirement: EnvironmentSettings,
    final_url: str | None = None,
) -> SessionState:
    missing_cookies = tuple(
        name for name in requirement.required_cookies if name not in cookie_names
    )
    headers_lower = {name.lower() for name in header_names}
    missing_headers = tuple(
        name for name in requirement.required_headers if name.lower() not in headers_lower
    )
    missing_any = (
        tuple(requirement.required_any_headers)
        if requirement.required_any_headers
        and (not any(name.lower() in headers_lower for name in requirement.required_any_headers))
        else ()
    )
    status = (
        SessionStatus.ESTABLISHED
        if page_opened and not missing_cookies and not missing_headers and not missing_any
        else SessionStatus.NOT_ESTABLISHED
    )
    return SessionState(
        status=status,
        cookie_names=cookie_names,
        header_names=header_names,
        final_url=final_url,
    )


class CjdkClient:
    """CJDK request format and session headers on top of the shared HTTP client."""

    def __init__(
        self,
        *,
        settings: config.CjdkJyrcSettings,
        observer: IntegrationObserver,
        trace_id: str,
        environment: str,
    ) -> None:
        self._settings = settings
        self._observer = observer
        self._trace_id = trace_id
        self.environment = environment
        self._environment = settings.environment(environment)
        self.base_url = (
            "https://cjdk-jyrc.mock"
            if settings.mode == "mock"
            else self._environment.agreement_base_url.rstrip("/")
        )
        self._http_client: HttpClient | None = None
        self._session_headers: dict[str, str] = {}
        self._session_state = SessionState()

    def open(self) -> None:
        limits = self._settings.response_limits
        transport: httpx.BaseTransport | None
        if self._settings.mode == "mock":
            transport = create_mock_transport()
        else:
            transport = httpx.HTTPTransport(verify=self._environment.verify_ssl)
        self._http_client = HttpClient(
            HttpClientConfig(
                base_url=self.base_url,
                timeout_seconds=django_settings.HTTP_TIMEOUT_SECONDS,
                connect_timeout_seconds=django_settings.HTTP_CONNECT_TIMEOUT_SECONDS,
                write_timeout_seconds=django_settings.HTTP_WRITE_TIMEOUT_SECONDS,
                pool_timeout_seconds=django_settings.HTTP_POOL_TIMEOUT_SECONDS,
                max_retries=django_settings.HTTP_MAX_RETRIES,
                retry_backoff_seconds=django_settings.HTTP_RETRY_BACKOFF_SECONDS,
                retry_max_backoff_seconds=django_settings.HTTP_RETRY_MAX_BACKOFF_SECONDS,
                follow_redirects=False,
                max_response_bytes=limits.max_json_bytes,
            ),
            transport=transport,
        )
    def close(self) -> None:
        if self._http_client is not None:
            self._http_client.close()
        self._http_client = None

    @property
    def state(self) -> SessionState:
        return self._session_state

    def acquire_session(self, application_url: str) -> SessionState:
        try:
            return self._acquire_session(application_url)
        except Exception:
            self._session_state = SessionState(status=SessionStatus.FAILED)
            raise

    def _extract_application_auth(self, application_url: str) -> str | None:
        parsed = urlsplit(application_url)
        query_candidates: list[str] = []
        if parsed.query:
            query_candidates.append(parsed.query)
        if "?" in parsed.fragment:
            (_, fragment_query) = parsed.fragment.split("?", 1)
            query_candidates.append(fragment_query)
        for query in query_candidates:
            auth_values = parse_qs(query, keep_blank_values=True).get("auth", [])
            if auth_values and auth_values[0].strip():
                return auth_values[0].strip()
        return None

    def _build_session_request_url(self, application_url: str, auth: str | None) -> str:
        template = self._environment.session_url_template
        if not template:
            return application_url
        if not auth:
            raise RuntimeError("申请链接中缺少有效的 auth 参数")
        return template.replace("{auth}", quote(auth, safe=""))

    def _acquire_session(self, application_url: str) -> SessionState:
        client = self._require_client()
        auth = self._extract_application_auth(application_url)
        session_request_url = self._build_session_request_url(application_url, auth)
        request_method = self._environment.session_method
        current_url = session_request_url
        page_opened = False
        redirect_limit = min(
            self._environment.max_redirects,
            self._settings.response_limits.max_redirects,
        )
        for redirect_count in range(redirect_limit + 1):
            page_headers = {"Accept": "application/json,text/plain,*/*"}
            if request_method == "POST":
                page_headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
            if may_forward_session_headers(current_url, self._environment):
                page_headers.update(self._session_headers)
            response = client.open_url(
                request_method,
                current_url,
                headers=page_headers,
                trace_id=self._trace_id,
                observer=self._observer,
                step="application_link.acquire_session",
            )
            if len(response.content) > self._settings.response_limits.max_html_bytes:
                raise RuntimeError(
                    f"Session 响应体超过上限 {self._settings.response_limits.max_html_bytes} bytes"
                )
            self._capture_session(dict(response.headers))
            page_opened = True
            if response.status_code not in REDIRECT_STATUSES:
                current_url = str(response.url)
                break
            location = response.headers.get("Location")
            if not location:
                raise RuntimeError("外系统重定向响应缺少 Location")
            if redirect_count >= redirect_limit:
                raise RuntimeError(f"外系统重定向次数超过上限 {redirect_limit}")
            current_url = urljoin(current_url, location)
            if response.status_code in {301, 302, 303}:
                request_method = "GET"
        self._session_state = self._evaluate_session(page_opened=page_opened, final_url=current_url)
        self._observer.diagnostic(
            step="application_link.acquire_session",
            title="Session 当前获取结果",
            content={
                "finalUrl": current_url,
                "cookieNames": list(self._session_state.cookie_names),
                "forwardedHeaderNames": list(self._session_state.header_names),
                "status": self._session_state.status.value,
            },
            level="INFO" if self._session_state.status == SessionStatus.ESTABLISHED else "ERROR",
        )
        return self._session_state

    def request(
        self, *, step: str, endpoint: EndpointSpec[ResponseModel], message: dict[str, Any]
    ) -> ResponseModel:
        client = self._require_client()
        if self._session_state.status != SessionStatus.ESTABLISHED:
            raise RuntimeError(
                "外系统 Session 未满足配置要求，不能请求协议接口；"
                f"当前状态={self._session_state.status.value}"
            )
        endpoint_url = urljoin(f"{self.base_url}/", endpoint.path.lstrip("/"))
        session_headers = (
            self._session_headers
            if may_forward_session_headers(endpoint_url, self._environment)
            else {}
        )
        serialized = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        result = client.request_detailed(
            endpoint.method,
            endpoint.path,
            response_model=endpoint.response_model,
            form_data={
                "msg_id": str(uuid.uuid4()),
                "sign": config.form_sign(),
                "timestamp": timezone.localtime().strftime(config.timestamp_format()),
                "REQ_MESSAGE": serialized,
                "biz_content": serialized,
            },
            headers={"Accept": "text/javascript;charset=utf-8", **session_headers},
            trace_id=self._trace_id,
            observer=self._observer,
            step=step,
            retry_mode=endpoint.retry_mode,
            response_validator=validate_cjdk_business_response,
        )
        self._capture_session(result.headers)
        self._session_state = self._evaluate_session(
            page_opened=True, final_url=self._session_state.final_url
        )
        return result.data

    def _evaluate_session(self, *, page_opened: bool, final_url: str | None) -> SessionState:
        http_cookie_names = self._http_client.cookie_names if self._http_client else ()
        return evaluate_session_state(
            page_opened=page_opened,
            cookie_names=http_cookie_names,
            header_names=tuple(sorted(self._session_headers)),
            requirement=self._environment.session,
            final_url=final_url,
        )

    def _capture_session(self, response_headers: Mapping[str, str]) -> None:
        normalized = {name.lower(): value for (name, value) in response_headers.items()}
        for header_name in SESSION_RESPONSE_HEADERS:
            value = normalized.get(header_name.lower())
            if value:
                self._session_headers[header_name] = value

    def _require_client(self) -> HttpClient:
        if self._http_client is None:
            raise RuntimeError("CjdkClient 必须在 with 块中使用")
        return self._http_client
