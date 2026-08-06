from __future__ import annotations

import json
import logging
import os
import re
import uuid
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, quote, urljoin, urlsplit

import httpx
from django.conf import settings as django_settings
from django.utils import timezone

from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.mock_transport import create_mock_transport
from apps.integrations.cjdk_jyrc.response import validate_cjdk_business_response
from apps.integrations.cjdk_jyrc.url_policy import (
    may_forward_session_headers,
    validate_external_url,
)
from apps.integrations.contracts import EndpointSpec, IntegrationObserver, ResponseModel
from apps.integrations.http import HttpCallObserver, HttpClient, HttpClientConfig
from apps.product_data.product_applications.contracts import SessionState, SessionStatus

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAMES = ("token_id", "JSESSIONID", "X-FCOS-SESSIONID")
SESSION_RESPONSE_HEADERS = ("X-Sd", "X-Token", "X-FCOS-SESSIONID")
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def evaluate_session_state(
    *,
    page_opened: bool,
    cookie_names: tuple[str, ...],
    header_names: tuple[str, ...],
    requirement: config.SessionRequirement,
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
        and not any(name.lower() in headers_lower for name in requirement.required_any_headers)
        else ()
    )
    configured = bool(
        requirement.required_cookies
        or requirement.required_headers
        or requirement.required_any_headers
    )
    if configured and not missing_cookies and not missing_headers and not missing_any:
        status = SessionStatus.ESTABLISHED
    elif cookie_names or header_names:
        status = SessionStatus.PARTIAL
    elif page_opened:
        status = SessionStatus.PAGE_OPENED
    else:
        status = SessionStatus.NOT_STARTED
    return SessionState(
        status=status,
        cookie_names=cookie_names,
        header_names=header_names,
        final_url=final_url,
        missing_cookies=missing_cookies,
        missing_headers=missing_headers,
        missing_any_headers=missing_any,
    )


class _StepObserver(HttpCallObserver):
    def __init__(self, observer: IntegrationObserver, step: str) -> None:
        self._observer = observer
        self._step = step

    def started(
        self,
        *,
        method: str,
        path: str,
        headers: Mapping[str, str],
        request_body: Any,
    ) -> object:
        return self._observer.request_started(
            step=self._step, method=method, url=path, headers=headers, body=request_body
        )

    def finished(
        self,
        handle: object,
        *,
        status_code: int | None,
        headers: Mapping[str, str],
        response_body: Any,
        duration_ms: int,
        error: Exception | None,
    ) -> None:
        self._observer.request_finished(
            handle,
            status_code=status_code,
            headers=headers,
            body=response_body,
            duration_ms=duration_ms,
            error=error,
        )


class CjdkJyrcClient:
    """Environment-bound CJDK HTTP session with explicit safety policy."""

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
        self._session_cookies: dict[str, str] = {}
        self._session_state = SessionState()

    def __enter__(self) -> CjdkJyrcClient:
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
        return self

    def __exit__(self, *_: object) -> None:
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
            _, fragment_query = parsed.fragment.split("?", 1)
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
        policy = self._environment.url_policy
        validate_external_url(application_url, policy)
        auth = self._extract_application_auth(application_url)
        session_request_url = self._build_session_request_url(application_url, auth)
        validate_external_url(session_request_url, policy)
        request_method = self._environment.session_method

        self._observer.diagnostic(
            step="application_link.acquire_session",
            title="Session 初始化入口",
            content={
                "currentImplementation": (
                    f"extract auth and {request_method} composed session URL"
                ),
                "sourceApplicationHost": urlsplit(application_url).hostname,
                "sessionRequestUrl": session_request_url.split("?", 1)[0],
                "authParameterPresent": bool(auth),
                "authParameterLength": len(auth) if auth else 0,
                "environment": self.environment,
            },
        )

        current_url = session_request_url
        previous_url: str | None = None
        chain: list[dict[str, Any]] = []
        page_opened = False
        redirect_limit = min(policy.max_redirects, self._settings.response_limits.max_redirects)
        raw_session_debug = (
            os.getenv("CJDK_SESSION_RAW_LOG", "false").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        for redirect_count in range(redirect_limit + 1):
            validate_external_url(current_url, policy, previous_url=previous_url)
            page_headers = {"Accept": "application/json,text/plain,*/*"}
            if request_method == "POST":
                page_headers["Content-Type"] = (
                    "application/x-www-form-urlencoded;charset=UTF-8"
                )
            if may_forward_session_headers(current_url, policy):
                page_headers.update(self._session_headers)
            else:
                page_headers["Cookie"] = ""

            if raw_session_debug:
                logger.warning("SESSION_RAW request_method=%s", request_method)
                logger.warning("SESSION_RAW request_url=%s", current_url)
                logger.warning("SESSION_RAW request_headers=%r", page_headers)

            response = client.open_url(
                request_method,
                current_url,
                headers=page_headers,
                trace_id=self._trace_id,
                observer=_StepObserver(self._observer, "application_link.acquire_session"),
            )
            if len(response.content) > self._settings.response_limits.max_html_bytes:
                raise RuntimeError(
                    f"Session 响应体超过上限 {self._settings.response_limits.max_html_bytes} bytes"
                )
            self._capture_session(
                dict(response.headers),
                set_cookie_values=tuple(response.headers.get_list("set-cookie")),
            )
            if raw_session_debug:
                logger.warning("SESSION_RAW response_status=%s", response.status_code)
                logger.warning(
                    "SESSION_RAW set_cookie=%r",
                    response.headers.get_list("set-cookie"),
                )
                logger.warning("SESSION_RAW response_headers=%r", dict(response.headers))

            chain.append(
                {
                    "statusCode": response.status_code,
                    "url": str(response.url),
                    "method": request_method,
                }
            )
            page_opened = True
            if response.status_code not in REDIRECT_STATUSES:
                current_url = str(response.url)
                break
            location = response.headers.get("Location")
            if not location:
                raise RuntimeError("外系统重定向响应缺少 Location")
            if redirect_count >= redirect_limit:
                raise RuntimeError(f"外系统重定向次数超过上限 {redirect_limit}")
            previous_url = current_url
            current_url = urljoin(current_url, location)
            if response.status_code in {301, 302, 303}:
                request_method = "GET"

        self._session_state = self._evaluate_session(page_opened=page_opened, final_url=current_url)
        self._observer.diagnostic(
            step="application_link.acquire_session",
            title="Session 当前获取结果",
            content={
                "redirectChain": chain,
                "finalUrl": current_url,
                "cookieNames": list(self._session_state.cookie_names),
                "forwardedHeaderNames": list(self._session_state.header_names),
                "status": self._session_state.status.value,
                "missingCookies": list(self._session_state.missing_cookies),
                "missingHeaders": list(self._session_state.missing_headers),
                "missingAnyHeaders": list(self._session_state.missing_any_headers),
                "sessionInitialized": (
                    self._session_state.status == SessionStatus.ESTABLISHED
                ),
            },
            level=("INFO" if self._session_state.status == SessionStatus.ESTABLISHED else "ERROR"),
        )
        return self._session_state

    def request(
        self,
        *,
        step: str,
        endpoint: EndpointSpec[ResponseModel],
        message: dict[str, Any],
    ) -> ResponseModel:
        client = self._require_client()
        if self._session_state.status != SessionStatus.ESTABLISHED:
            raise RuntimeError(
                "外系统 Session 未满足配置要求，不能请求协议接口；"
                f"当前状态={self._session_state.status.value}"
            )
        endpoint_url = urljoin(f"{self.base_url}/", endpoint.path.lstrip("/"))
        validate_external_url(endpoint_url, self._environment.url_policy)
        session_headers = (
            self._session_headers
            if may_forward_session_headers(endpoint_url, self._environment.url_policy)
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
            observer=_StepObserver(self._observer, step),
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
        cookies = tuple(sorted(set(http_cookie_names) | set(self._session_cookies)))
        headers = tuple(
            sorted(name for name in self._session_headers if name.lower() != "cookie")
        )
        return evaluate_session_state(
            page_opened=page_opened,
            cookie_names=cookies,
            header_names=headers,
            requirement=self._environment.session,
            final_url=final_url,
        )

    def _capture_session(
        self,
        response_headers: Mapping[str, str],
        *,
        set_cookie_values: tuple[str, ...] = (),
    ) -> None:
        normalized = {name.lower(): value for name, value in response_headers.items()}
        raw_set_cookie = "\n".join(set_cookie_values) or normalized.get("set-cookie", "")
        target_cookie_names = tuple(
            dict.fromkeys((*SESSION_COOKIE_NAMES, *self._environment.session.required_cookies))
        )
        for cookie_name in target_cookie_names:
            pattern = (
                rf"(?i)(?:^|[\r\n,;]\s*){re.escape(cookie_name)}=([^;,\r\n]+)"
            )
            match = re.search(pattern, raw_set_cookie)
            if match:
                self._session_cookies[cookie_name] = match.group(1).strip()

        if self._session_cookies:
            self._session_headers["Cookie"] = "; ".join(
                f"{cookie_name}={self._session_cookies[cookie_name]}"
                for cookie_name in target_cookie_names
                if cookie_name in self._session_cookies
            )

        for header_name in SESSION_RESPONSE_HEADERS:
            value = normalized.get(header_name.lower())
            if value:
                self._session_headers[header_name] = value

    def _require_client(self) -> HttpClient:
        if self._http_client is None:
            raise RuntimeError("CjdkJyrcClient 必须在 with 块中使用")
        return self._http_client
