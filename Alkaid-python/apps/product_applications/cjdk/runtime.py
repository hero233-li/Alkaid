from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import uuid
from collections.abc import Callable, Mapping
from copy import deepcopy
from enum import Enum
from functools import cache, lru_cache
from pathlib import Path
from time import monotonic
from typing import Any, Literal
from urllib.parse import parse_qs, quote, urljoin, urlsplit

import httpx
from django.conf import settings as django_settings
from django.utils import timezone
from pydantic import BaseModel, ConfigDict, Field

from apps.integrations.contracts import (
    BusinessResponseError,
    EndpointSpec,
    IntegrationObserver,
    ResponseModel,
    RetryMode,
)
from apps.integrations.http import HttpCallObserver, HttpClient, HttpClientConfig
from apps.product_applications.cjdk import config
from apps.product_applications.cjdk.config import EnvironmentSettings, get_identity_settings
from apps.product_applications.cjdk.mock import create_mock_transport, mock_submit_application
from apps.product_data.catalog import FrozenApplicationLinkRoute, ProductExecutionSnapshot

ApplicationLinkKind = Literal["internal", "external"]
ApplicationSubmission = tuple[str, str, str]
ProgressReporter = Callable[..., None]


class SessionStatus(str, Enum):
    NOT_STARTED = "not_started"
    PAGE_OPENED = "page_opened"
    PARTIAL = "partial"
    ESTABLISHED = "established"
    FAILED = "failed"


class SessionState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SessionStatus = SessionStatus.NOT_STARTED
    cookie_names: tuple[str, ...] = ()
    header_names: tuple[str, ...] = ()
    final_url: str | None = None
    missing_cookies: tuple[str, ...] = ()
    missing_headers: tuple[str, ...] = ()
    missing_any_headers: tuple[str, ...] = ()


class UnsafeExternalUrl(ValueError):
    pass


def validate_external_url(
    url: str, policy: EnvironmentSettings, *, previous_url: str | None = None
) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeExternalUrl(f"外系统 URL 无效：{exc}") from exc
    if parsed.username or parsed.password:
        raise UnsafeExternalUrl("外系统 URL 禁止包含用户名或密码")
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    effective_port = port or (443 if scheme == "https" else 80)
    if scheme not in policy.allowed_schemes:
        raise UnsafeExternalUrl(f"外系统 URL scheme 未获允许：{scheme or 'missing'}")
    allowed_hosts = {item.lower().rstrip(".") for item in policy.allowed_hosts}
    if host not in allowed_hosts:
        raise UnsafeExternalUrl(f"外系统 URL host 未获允许：{host or 'missing'}")
    if effective_port not in policy.allowed_ports:
        raise UnsafeExternalUrl(f"外系统 URL port 未获允许：{effective_port}")
    if previous_url and (not policy.allow_cross_host_redirect):
        previous_host = (urlsplit(previous_url).hostname or "").lower().rstrip(".")
        if host != previous_host:
            raise UnsafeExternalUrl(f"外系统重定向到不同 host：{previous_host} -> {host}")
    return url


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


logger = logging.getLogger(__name__)
SESSION_COOKIE_NAMES = ("token_id", "JSESSIONID", "X-FCOS-SESSIONID")
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
    configured = bool(
        requirement.required_cookies
        or requirement.required_headers
        or requirement.required_any_headers
    )
    if configured and (not missing_cookies) and (not missing_headers) and (not missing_any):
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
        self, *, method: str, path: str, headers: Mapping[str, str], request_body: Any
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


class CjdkClient:
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

    def __enter__(self) -> CjdkClient:
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
                "currentImplementation": f"extract auth and {request_method} composed session URL",
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
        raw_session_debug = os.getenv("CJDK_SESSION_RAW_LOG", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        for redirect_count in range(redirect_limit + 1):
            validate_external_url(current_url, policy, previous_url=previous_url)
            page_headers = {"Accept": "application/json,text/plain,*/*"}
            if request_method == "POST":
                page_headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
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
                logger.warning("SESSION_RAW set_cookie=%r", response.headers.get_list("set-cookie"))
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
                "sessionInitialized": self._session_state.status == SessionStatus.ESTABLISHED,
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
        headers = tuple(sorted(name for name in self._session_headers if name.lower() != "cookie"))
        return evaluate_session_state(
            page_opened=page_opened,
            cookie_names=cookies,
            header_names=headers,
            requirement=self._environment.session,
            final_url=final_url,
        )

    def _capture_session(
        self, response_headers: Mapping[str, str], *, set_cookie_values: tuple[str, ...] = ()
    ) -> None:
        normalized = {name.lower(): value for (name, value) in response_headers.items()}
        raw_set_cookie = "\n".join(set_cookie_values) or normalized.get("set-cookie", "")
        target_cookie_names = tuple(
            dict.fromkeys((*SESSION_COOKIE_NAMES, *self._environment.session.required_cookies))
        )
        for cookie_name in target_cookie_names:
            pattern = f"(?i)(?:^|[\\r\\n,;]\\s*){re.escape(cookie_name)}=([^;,\\r\\n]+)"
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
            raise RuntimeError("CjdkClient 必须在 with 块中使用")
        return self._http_client


class ProductApplicationRuntime:
    """One workflow port set; CJDK, Photo and DCPP retain separate clients."""

    def __init__(
        self,
        *,
        settings: config.CjdkJyrcSettings,
        observer: IntegrationObserver,
        trace_id: str,
        environment: str,
    ) -> None:
        from apps.product_applications.cjdk.identity import DcppClient, PhotoClient

        client = CjdkClient(
            settings=settings, observer=observer, trace_id=trace_id, environment=environment
        )
        self._client = client
        self._settings = settings
        self._observer = observer
        self._trace_id = trace_id
        self._identity_settings = get_identity_settings(settings.mode)
        self._photo_client = None
        self._dcpp_client = None
        if not self._identity_settings.mock:
            photo_settings = self._identity_settings.photo_environment(environment)
            self._photo_client = PhotoClient(photo_settings)
            self._dcpp_client = DcppClient(self._identity_settings.sms_lookup)

    def __enter__(self) -> ProductApplicationRuntime:
        self._client.__enter__()
        try:
            if self._photo_client is not None:
                self._photo_client.__enter__()
            if self._dcpp_client is not None:
                self._dcpp_client.__enter__()
        except Exception:
            self._client.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args: object) -> None:
        try:
            if self._photo_client is not None:
                self._photo_client.__exit__(*args)
            if self._dcpp_client is not None:
                self._dcpp_client.__exit__(*args)
        finally:
            self._client.__exit__(*args)

    def open_application(
        self,
        *,
        snapshot: ProductExecutionSnapshot,
        application_link_kind: ApplicationLinkKind,
        progress: ProgressReporter | None = None,
    ) -> dict[str, Any]:
        links = generate_application_link(
            plan=snapshot.application_link_route,
            normalized_payload=snapshot.normalized_payload,
            observer=self._observer,
            trace_id=self._trace_id,
        )
        _report(progress, "application_link", 40, "申请链接获取完成")
        application_url = links[f"{application_link_kind}_url"]
        session = self._client.acquire_session(application_url)
        if session.status != SessionStatus.ESTABLISHED:
            raise RuntimeError(
                "外系统 Session 未满足配置要求，停止协议查询；"
                f"当前状态={session.status.value}；"
                f"缺少 Cookie={list(session.missing_cookies)}；"
                f"缺少 Header={list(session.missing_headers)}；"
                f"任一 Header 要求={list(session.missing_any_headers)}"
            )
        _report(progress, "session", 50, "申请页面 Session 建立完成")
        return {
            "applicationLinkCategory": snapshot.application_link_route.category_code.display_name,
            "selectedApplicationLinkKind": application_link_kind,
            "session": session,
        }

    def read_agreements(
        self,
        *,
        payload: Mapping[str, Any],
        progress: ProgressReporter | None = None,
    ) -> dict[str, Any]:
        return self._read_agreements(payload=payload, progress=progress)

    def _read_agreements(
        self,
        *,
        payload: Mapping[str, Any],
        scene: str | None = None,
        stage_prefix: str = "agreement",
        progress_points: tuple[int, int, int] = (65, 78, 90),
        progress: ProgressReporter | None = None,
    ) -> dict[str, Any]:
        query_progress, preview_progress, read_progress = progress_points
        templates = query_agreement_templates(self._client, self._settings, payload, scene=scene)
        _report(progress, f"{stage_prefix}_query", query_progress, "协议模板查询完成")
        preview = query_agreement_preview(self._client, self._settings, payload, templates)
        _report(progress, f"{stage_prefix}_preview", preview_progress, "协议预览生成完成")
        doc_ids = (
            (str(preview["docId"]),)
            if preview.get("docId")
            else tuple(
                str(document["docId"]) for document in preview["documents"] if document.get("docId")
            )
        )
        if not doc_ids:
            raise RuntimeError("协议预览成功，但没有可用于读取协议的 docId")
        documents = read_agreement_documents(self._client, self._settings, doc_ids)
        _report(progress, f"{stage_prefix}_read", read_progress, "协议阅读完成")
        return {
            "agreementTemplates": templates,
            "agreementPreview": preview,
            "agreementDocuments": documents,
            "session": self._client.state,
        }

    def submit_application(
        self,
        *,
        payload: Mapping[str, Any],
        progress: ProgressReporter | None = None,
    ) -> ApplicationSubmission:
        if self._settings.mode == "mock":
            result = mock_submit_application(payload)
            _report(progress, "application_submit", 90, "申请提交完成")
            return result
        raise RuntimeError(
            "真实模式缺少 startApply 接口路径和原始报文模板；请补齐 CJDK 配置后再启用真实产品申请"
        )

    def verify_identity(
        self,
        *,
        payload: Mapping[str, Any],
        environment: str,
        submission: ApplicationSubmission,
        progress: ProgressReporter | None = None,
    ) -> None:
        from apps.product_applications.cjdk.identity import execute_identity_verification

        execute_identity_verification(
            client=self._client,
            settings=self._identity_settings,
            payload=payload,
            environment=environment,
            submission=submission,
            read_agreements=self._read_agreements,
            delete_photo=self._delete_certificate_photo,
            find_sms_code=self._find_sms_code,
            progress=progress,
        )

    def _delete_certificate_photo(self, *, identity_no: str) -> None:
        if self._identity_settings.mock:
            return
        assert self._photo_client is not None
        self._photo_client.delete_certificate_photo(identity_no=identity_no)

    def _find_sms_code(self, *, environment: str, mobile: str, pass_code_seq: str) -> str:
        if self._identity_settings.mock:
            return "123456"
        assert self._dcpp_client is not None
        return self._dcpp_client.find_sms_code(
            environment=environment, mobile=mobile, pass_code_seq=pass_code_seq
        )


def _report(reporter: ProgressReporter | None, stage: str, progress: int, message: str) -> None:
    if reporter is not None:
        reporter(stage=stage, progress=progress, message=message)


class CjdkEnvelope(BaseModel):
    """The only typed CJDK wire boundary; endpoint fields are parsed below."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    rsp_body: dict[str, Any] = Field(alias="RSP_BODY")
    rsp_head: dict[str, Any] = Field(default_factory=dict, alias="RSP_HEAD")


QUERY_AGREEMENT_TEMPLATES = EndpointSpec(
    operation_id="cjdk_jyrc.query_agreement_templates",
    method="POST",
    path="/h5/microservice/queryAgreementTemplateInfoListEA.do",
    response_model=CjdkEnvelope,
    retry_mode=RetryMode.NEVER,
)
QUERY_PREVIEW_IMAGE = EndpointSpec(
    operation_id="cjdk_jyrc.query_preview_image",
    method="POST",
    path="/h5/microservice/queryPreviewImage.ajax",
    response_model=CjdkEnvelope,
    retry_mode=RetryMode.NEVER,
)
SHOW_DOCUMENT_BY_DOC_ID = EndpointSpec(
    operation_id="cjdk_jyrc.show_document_by_doc_id",
    method="POST",
    path="/h5/microservice/showDocumentByDocIdList.ajax",
    response_model=CjdkEnvelope,
    retry_mode=RetryMode.NEVER,
)
AGREEMENT_ENDPOINTS = (QUERY_AGREEMENT_TEMPLATES, QUERY_PREVIEW_IMAGE, SHOW_DOCUMENT_BY_DOC_ID)
RAW_MESSAGE_ROOT = Path(__file__).with_name("raw_messages")


def new_message(name: str) -> dict[str, Any]:
    try:
        return deepcopy(_message_catalog()[name])
    except KeyError:
        raise KeyError(f"未配置 CJDK-JYRC 原始报文：{name}") from None


@lru_cache(maxsize=1)
def _message_catalog() -> dict[str, dict[str, Any]]:
    messages: dict[str, dict[str, Any]] = {}
    for path in sorted(RAW_MESSAGE_ROOT.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"CJDK-JYRC {path.name} 必须是 JSON 对象")
        for name, message in raw.items():
            if not isinstance(message, dict):
                raise ValueError(f"CJDK-JYRC 报文 {name} 必须是 JSON 对象")
            key = str(name)
            if key in messages:
                raise ValueError(f"CJDK-JYRC 原始报文重复：{key}")
            messages[key] = message
    return messages


def validate_message_catalog() -> dict[str, int]:
    catalog = _message_catalog()
    required = {
        "query_agreement_templates_v1",
        "query_preview_image_v1",
        "show_document_by_doc_id_v1",
        "identity_get_public_key_v1",
        "identity_get_prepare_mobile_v1",
        "identity_ali_sdk_params_v1",
        "identity_ali_video_check_u12_v1",
        "identity_ali_video_check_uc_v1",
        "identity_sms_code_send_v1",
        "identity_sms_code_check_v1",
        "identity_card_verify_v1",
    }
    missing = required - catalog.keys()
    if missing:
        raise ValueError(f"CJDK-JYRC 缺少原始报文：{', '.join(sorted(missing))}")
    return {"messages": len(catalog)}


PROFILE_ROOT = Path(__file__).with_name("profiles")


class ApplicationConfigurationError(ValueError):
    pass


class IntegrationProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)
    id: str = Field(min_length=1, max_length=255)
    version: int = Field(ge=1)
    checksum: str = Field(pattern="^sha256:[0-9a-f]{64}$")
    template: dict[str, Any]
    secret_bindings: dict[str, str] = Field(default_factory=dict, alias="secretBindings")


def load_integration_profile(
    profile_id: str, version: int, profile_root: Path | None = None
) -> IntegrationProfile:
    if profile_root is None:
        return _load_default_integration_profile(profile_id, version)
    return _load_integration_profile(profile_id, version, profile_root)


@cache
def _load_default_integration_profile(profile_id: str, version: int) -> IntegrationProfile:
    return _load_integration_profile(profile_id, version, PROFILE_ROOT)


def _load_integration_profile(
    profile_id: str, version: int, profile_root: Path
) -> IntegrationProfile:
    matches: list[tuple[Path, IntegrationProfile]] = []
    for path in sorted(profile_root.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            encoded = json.dumps(
                raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            profile = IntegrationProfile.model_validate(
                {**raw, "checksum": f"sha256:{hashlib.sha256(encoded).hexdigest()}"}
            )
        except (OSError, ValueError) as exc:
            raise ApplicationConfigurationError(
                f"Integration Profile 无效：{path.name}: {exc}"
            ) from exc
        if profile.id == profile_id and profile.version == version:
            matches.append((path, profile))
    if not matches:
        raise ApplicationConfigurationError(f"未知 Integration Profile：{profile_id}@{version}")
    if len(matches) > 1:
        names = ", ".join(path.name for (path, _) in matches)
        raise ApplicationConfigurationError(
            f"Integration Profile 重复：{profile_id}@{version}: {names}"
        )
    return matches[0][1]


_MISSING = object()


def build_application_link_request(
    *,
    plan: FrozenApplicationLinkRoute,
    normalized_payload: dict[str, Any],
    secret_resolver: Any | None = None,
) -> dict[str, Any]:
    bound_payload = deepcopy(plan.compiled_request_template)
    missing = [field for field in plan.required_fields if _is_blank(normalized_payload.get(field))]
    if missing:
        raise ApplicationConfigurationError("申请链接缺少必填字段：" + ", ".join(sorted(missing)))
    for target, source in plan.payload_bindings.items():
        value = _runtime_value(
            source,
            product=normalized_payload.get("product"),
            environment=plan.environment,
            category=plan.category_code.display_name,
            normalized_payload=normalized_payload,
        )
        if value is _MISSING:
            continue
        _set_value(bound_payload, target, deepcopy(value))
    for target, reference in plan.secret_bindings.items():
        try:
            if secret_resolver is None:
                secret_value = config.resolve_secret(reference)
            elif callable(secret_resolver):
                secret_value = secret_resolver(reference)
            else:
                secret_value = secret_resolver.resolve(reference)
        except (KeyError, ValueError) as exc:
            raise ApplicationConfigurationError(f"申请链接秘密配置不可用：{reference}") from exc
        if not secret_value:
            raise ApplicationConfigurationError(f"申请链接秘密配置为空：{reference}")
        _set_value(bound_payload, target, secret_value)
    project_id = normalized_payload.get("cooperationProjectId")
    request = {
        "env": plan.environment,
        "product": str(normalized_payload.get("product") or ""),
        "category": plan.category_code.display_name,
        "payload": bound_payload,
    }
    if project_id not in {None, ""}:
        request["cooperationProjectId"] = str(project_id).strip()
    return request


def _runtime_value(
    source: str,
    *,
    product: object,
    environment: str,
    category: str,
    normalized_payload: dict[str, Any],
) -> Any:
    if source == "product":
        return product
    if source == "environment":
        return environment
    if source == "category":
        return category
    if source == "payload":
        return normalized_payload
    if source.startswith("payload."):
        return _get_value(normalized_payload, source.removeprefix("payload."))
    if source in normalized_payload:
        return normalized_payload[source]
    raise ApplicationConfigurationError(f"申请链接绑定来源不存在：{source}")


def _get_value(content: Mapping[str, Any], path: str) -> Any:
    current: Any = content
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ApplicationConfigurationError(f"申请链接绑定来源不存在：payload.{path}")
        current = current[part]
    return current


def _set_value(content: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ApplicationConfigurationError("申请链接绑定目标路径不能为空")
    current = content
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            raise ApplicationConfigurationError(f"申请链接绑定目标不是 JSON 对象：{path}")
        current = child
    current[parts[-1]] = value


def _is_blank(value: Any) -> bool:
    return value is None or value == ""


logger = logging.getLogger(__name__)
RESULT_PREFIX = "ALKAID_RESULT="


def generate_application_link(
    *,
    plan: FrozenApplicationLinkRoute,
    normalized_payload: Mapping[str, Any],
    observer: IntegrationObserver,
    trace_id: str,
) -> dict[str, str]:
    """Build the request and invoke the local Java SDK without a gateway object."""

    integration_settings = config.get_cjdk_jyrc_settings()
    java_request = build_application_link_request(
        plan=plan, normalized_payload=dict(normalized_payload)
    )
    call_path = (
        "mock://java-application-link"
        if integration_settings.mode == "mock"
        else integration_settings.java_gateway.main_class
    )
    handle = observer.request_started(
        step="application_link.generate_link",
        method="JAVA",
        url=call_path,
        headers={},
        body=java_request,
    )
    started_at = monotonic()
    logger.info(
        "application_link_java_started",
        extra={
            "trace_id": trace_id,
            "env": java_request["env"],
            "product": java_request["product"],
            "category": java_request["category"],
            "cooperation_project_id": java_request.get("cooperationProjectId"),
            "payload_fields": sorted(java_request["payload"]),
        },
    )
    try:
        raw = (
            _mock_java_result(java_request)
            if integration_settings.mode == "mock"
            else execute_java(java_request)
        )
        internal_url = _required_link(raw, "internal_url", "internalUrl")
        external_url = _required_link(raw, "external_url", "externalUrl")
        links = {"internal_url": internal_url, "external_url": external_url}
    except Exception as exc:
        observer.request_finished(
            handle,
            status_code=None,
            headers={},
            body={},
            duration_ms=_duration_ms(started_at),
            error=exc,
        )
        raise
    observer.request_finished(
        handle,
        status_code=0,
        headers={},
        body=links,
        duration_ms=_duration_ms(started_at),
        error=None,
    )
    logger.info("application_link_java_completed", extra={"trace_id": trace_id})
    return links


def execute_java(java_request: dict[str, Any]) -> dict[str, Any]:
    settings = config.get_cjdk_jyrc_settings().java_gateway
    sdk_root = settings.sdk_dir
    java_executable = _resolve_runtime_path(settings.java_executable, sdk_root)
    jar_path = _resolve_runtime_path(settings.jar, sdk_root)
    _validate_java_runtime(sdk_root=sdk_root, java_executable=java_executable, jar_path=jar_path)
    classpath = os.pathsep.join([str(jar_path), str(sdk_root / "lib" / "*")])
    with tempfile.TemporaryDirectory(prefix="alkaid-link-") as temp_dir:
        request_path = Path(temp_dir) / "request.json"
        request_path.write_text(
            json.dumps(java_request, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        command = [str(java_executable), "-cp", classpath, settings.main_class, str(request_path)]
        try:
            completed = subprocess.run(
                command,
                cwd=str(sdk_root),
                shell=False,
                capture_output=True,
                text=True,
                encoding=settings.output_encoding,
                errors="replace",
                timeout=settings.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"申请链接 Java SDK 执行超时：{settings.timeout_seconds} 秒"
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"申请链接 Java SDK 无法启动：{exc}") from exc
    if completed.returncode != 0:
        error_tail = completed.stderr[-2000:]
        raise RuntimeError(
            f"申请链接 Java SDK 执行失败：exit_code={completed.returncode}; stderr={error_tail}"
        )
    return parse_java_result(completed.stdout)


def parse_java_result(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        normalized = line.strip()
        if normalized.startswith(RESULT_PREFIX):
            try:
                result = json.loads(normalized[len(RESULT_PREFIX) :])
            except json.JSONDecodeError as exc:
                raise RuntimeError("Java ALKAID_RESULT 不是有效 JSON") from exc
            if not isinstance(result, dict):
                raise RuntimeError("Java 返回结果不是 JSON 对象")
            return result
    raise RuntimeError("Java 执行成功，但没有输出 ALKAID_RESULT")


def _required_link(source: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    raise RuntimeError(f"Java 返回缺少申请链接：{'/'.join(keys)}")


def _validate_java_runtime(*, sdk_root: Path, java_executable: Path, jar_path: Path) -> None:
    if not sdk_root.exists():
        raise RuntimeError(f"Java SDK 目录不存在：{sdk_root}")
    if not java_executable.exists():
        raise RuntimeError(f"Java 可执行文件不存在：{java_executable}")
    if not jar_path.exists():
        raise RuntimeError(f"申请链接 Jar 不存在：{jar_path}")


def _resolve_runtime_path(value: Path, sdk_root: Path) -> Path:
    return value if value.is_absolute() else sdk_root / value


def _mock_java_result(java_request: dict[str, Any]) -> dict[str, str]:
    digest = (
        hashlib.sha256(json.dumps(java_request, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        .hexdigest()[:12]
        .upper()
    )
    link_id = f"LINK-{digest}"
    return {
        "internal_url": f"https://cjdk-jyrc.mock/application-entry/{link_id}",
        "external_url": f"https://cjdk-jyrc.mock/application-entry/{link_id}?scope=external",
    }


def _duration_ms(started_at: float) -> int:
    return max(0, int((monotonic() - started_at) * 1000))


class CjdkProtocolError(RuntimeError):
    pass


def _optional_payload_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _required_payload_text(payload: Mapping[str, Any], key: str, label: str) -> str:
    value = _optional_payload_text(payload, key)
    if value is None:
        raise CjdkProtocolError(f"当前任务缺少{label}：{key}")
    return value


def query_agreement_templates(
    client: CjdkClient,
    settings: config.CjdkJyrcSettings,
    payload: Mapping[str, Any],
    *,
    scene: str | None = None,
) -> tuple[dict[str, Any], ...]:
    message = new_message("query_agreement_templates_v1")
    request = message["REQ_BODY"]["request"]
    product_id = _required_payload_text(payload, "product", "产品编号")
    cooperation_project_id = _optional_payload_text(payload, "cooperationProjectId")
    request.update(
        {
            "x-channel": config.channel(),
            "scene": scene or config.scene(),
            "selbProdId": product_id,
            "branchId": str(payload["branch"]),
            "prodSubdvDmsn": config.product_subdivision(),
        }
    )
    request.pop("prodSubdvDmsnEncode", None)
    if cooperation_project_id is not None:
        request["prodSubdvDmsnEncode"] = cooperation_project_id
    response = client.request(
        step="agreement.query_templates", endpoint=QUERY_AGREEMENT_TEMPLATES, message=message
    )
    response_data = required_mapping(response.rsp_body, "response")
    templates = required_list(response_data, "docAgreementTemplateInfoList")
    if not templates:
        raise CjdkProtocolError("查询协议成功，但未返回协议模板")
    limit = settings.response_limits.max_agreement_templates
    if len(templates) > limit:
        raise CjdkProtocolError(f"协议模板返回 {len(templates)} 个，超过上限 {limit}")
    return tuple(
        {
            "docId": required_text(item, "docId"),
            "docName": optional_text(item, "docName"),
            "docType": optional_text(item, "docType"),
            "fcosTemplateNo": optional_text(item, "fcosTemplateNo"),
            "status": optional_text(item, "status"),
        }
        for item in templates
    )


def query_agreement_preview(
    client: CjdkClient,
    settings: config.CjdkJyrcSettings,
    payload: Mapping[str, Any],
    templates: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    template_numbers = [
        str(item["fcosTemplateNo"]) for item in templates if item.get("fcosTemplateNo")
    ] or list(config.default_template_numbers())
    if not template_numbers:
        raise CjdkProtocolError("没有可用于生成协议预览的模板编号")
    message = new_message("query_preview_image_v1")
    request = message["REQ_BODY"]["request"]
    auth_values = {
        "custNme": str(payload.get("personName") or ""),
        "idNo": str(payload.get("certificateNo") or ""),
        "orgCode": str(payload.get("branch") or ""),
    }
    id_type = str(payload.get("idType") or config.default_id_type()).strip()
    if id_type:
        auth_values["idType"] = id_type
    template_auth_variables = request.get("authVariableList", [])
    request["authVariableList"] = [
        {
            **item,
            "value": auth_values.get(str(item.get("code") or ""), str(item.get("value") or "")),
        }
        for item in template_auth_variables
    ]
    product_id = _required_payload_text(payload, "product", "产品编号")
    request.update(
        {
            "x-channel": config.channel(),
            "selbProdId": product_id,
            "businessNo": config.business_no(),
            "fcosTemplateNoList": [{"fcosTemplateNo": number} for number in template_numbers],
        }
    )
    cooperation_project_id = _optional_payload_text(payload, "cooperationProjectId")
    request.pop("coprProjeId", None)
    request.pop("prodSubdvDmsnEncode", None)
    if cooperation_project_id is not None:
        request["prodSubdvDmsnEncode"] = cooperation_project_id
    response = client.request(
        step="agreement.query_preview", endpoint=QUERY_PREVIEW_IMAGE, message=message
    )
    preview = required_mapping(response.rsp_body, "response")
    success_flag = required_text(preview, "successFlag")
    if success_flag != "Y":
        raise CjdkProtocolError(
            f"协议预览生成失败：{optional_text(preview, 'message') or success_flag}"
        )
    documents = required_list(preview, "docList", allow_missing=True)
    preview_doc_id = optional_text(preview, "docId")
    if not documents and preview_doc_id:
        documents.append({"docId": preview_doc_id})
    if not documents:
        raise CjdkProtocolError("协议预览成功，但未返回 docId")
    limit = settings.response_limits.max_preview_documents
    if len(documents) > limit:
        raise CjdkProtocolError(f"协议预览返回 {len(documents)} 个文档，超过上限 {limit}")
    return {
        "successFlag": success_flag,
        "docId": preview_doc_id,
        "documents": tuple(
            {
                "docId": required_text(item, "docId"),
                "docName": optional_text(item, "docName"),
                "docType": optional_text(item, "docType"),
                "fcosTemplateNo": optional_text(item, "fcosTemplateNo"),
            }
            for item in documents
        ),
    }


def read_agreement_documents(
    client: CjdkClient,
    settings: config.CjdkJyrcSettings,
    doc_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    documents: list[dict[str, Any]] = []
    total_document_bytes = 0
    total_limit = settings.response_limits.max_total_document_bytes
    for doc_id in doc_ids:
        document = read_agreement_document(client, settings, doc_id)
        total_document_bytes += int(document.get("contentBytes") or 0)
        if total_document_bytes > total_limit:
            raise CjdkProtocolError(f"所有协议文档累计超过 {total_limit} bytes")
        documents.append(document)
    return tuple(documents)


def read_agreement_document(
    client: CjdkClient, settings: config.CjdkJyrcSettings, doc_id: str
) -> dict[str, Any]:
    message = new_message("show_document_by_doc_id_v1")
    message["REQ_BODY"]["request"].update(
        {"x-channel": config.channel(), "docId": doc_id, "TransCode": ""}
    )
    response = client.request(
        step="agreement.read_document", endpoint=SHOW_DOCUMENT_BY_DOC_ID, message=message
    )
    document = response.rsp_body
    success_flag = required_text(document, "successFlag")
    if success_flag != "Y":
        raise CjdkProtocolError(f"读取协议失败：successFlag={success_flag}")
    file_items = required_list(document, "fileInfo", allow_missing=True)
    file_info = file_items[0] if file_items else {}
    content = optional_text(document, "downFile") or optional_text(file_info, "downFile")
    if not content:
        raise CjdkProtocolError("读取协议成功，但未返回协议文件内容")
    content_bytes = validated_decoded_size(settings, doc_id, content)
    return {
        "docId": doc_id,
        "fileName": optional_text(file_info, "fileName"),
        "docSize": optional_text(document, "docSize"),
        "successFlag": success_flag,
        "contentBytes": content_bytes,
    }


def validated_decoded_size(settings: config.CjdkJyrcSettings, doc_id: str, content: str) -> int:
    limits = settings.response_limits
    if len(content) > limits.max_base64_characters:
        raise CjdkProtocolError(
            f"文档 {doc_id} Base64 字符长度超过上限 {limits.max_base64_characters}"
        )
    estimated = len(content) * 3 // 4
    if estimated > limits.max_decoded_document_bytes:
        raise CjdkProtocolError(
            f"文档 {doc_id} 解码后大小超过 {limits.max_decoded_document_bytes} bytes"
        )
    try:
        decoded_size = len(base64.b64decode(content, validate=True))
    except (ValueError, binascii.Error) as exc:
        raise CjdkProtocolError(f"文档 {doc_id} 不是有效 Base64") from exc
    if decoded_size > limits.max_decoded_document_bytes:
        raise CjdkProtocolError(
            f"文档 {doc_id} 解码后大小超过 {limits.max_decoded_document_bytes} bytes"
        )
    return decoded_size


def required_mapping(source: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = source.get(key)
    if not isinstance(value, Mapping):
        raise CjdkProtocolError(f"外系统响应缺少对象字段：{key}")
    return dict(value)


def required_list(
    source: Mapping[str, Any], key: str, *, allow_missing: bool = False
) -> list[dict[str, Any]]:
    value = source.get(key)
    if value is None and allow_missing:
        return []
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise CjdkProtocolError(f"外系统响应字段必须是对象列表：{key}")
    return [dict(item) for item in value]


def optional_text(source: Mapping[str, Any], key: str) -> str | None:
    value = source.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def required_text(source: Mapping[str, Any], key: str) -> str:
    value = optional_text(source, key)
    if value is None:
        raise CjdkProtocolError(f"外系统响应缺少文本字段：{key}")
    return value


def compile_application_link_plan(
    *, catalog: Any, product_code: str, environment: str, method_code: str
) -> FrozenApplicationLinkRoute:
    product = catalog.product(product_code)
    method = product.method(method_code)
    normalized_environment = environment.strip().upper()
    if normalized_environment not in product.environments:
        raise ApplicationConfigurationError(
            f"产品 {product.code} 不支持环境：{normalized_environment}"
        )
    matches = [
        route
        for route in product.features.application_links
        if route.environment == normalized_environment
        and ("*" in route.application_methods or method.code in route.application_methods)
    ]
    if not matches:
        raise ApplicationConfigurationError(
            f"产品 {product.code} 在环境 {normalized_environment}、"
            f"申请方式 {method.code} 未配置申请链接路由"
        )
    if len(matches) > 1:
        raise ApplicationConfigurationError(
            f"产品 {product.code} 在环境 {normalized_environment}、"
            f"申请方式 {method.code} 匹配到多条申请链接路由"
        )
    route = matches[0]
    try:
        profile = load_integration_profile(
            route.integration_profile_id, route.integration_profile_version
        )
    except ValueError as exc:
        raise ApplicationConfigurationError(str(exc)) from exc
    enabled_fields = {field.name for field in product.enabled_execution_fields(method.code)}
    unknown_required = set(route.required_fields) - enabled_fields
    if unknown_required:
        raise ApplicationConfigurationError(
            f"路由 {route.route_id} 的必填字段未在当前产品/申请方式启用："
            f"{', '.join(sorted(unknown_required))}"
        )
    for secret_path in profile.secret_bindings:
        if not _path_exists(profile.template, secret_path):
            raise ApplicationConfigurationError(
                f"Profile {profile.id}@{profile.version} 的秘密字段路径不存在：{secret_path}"
            )
        if _path_exists(route.request_template, secret_path):
            raise ApplicationConfigurationError(
                f"路由 {route.route_id} 不允许覆盖秘密字段：{secret_path}"
            )
    compiled_template = deepcopy(profile.template)
    _deep_merge(compiled_template, route.request_template)
    for secret_path in profile.secret_bindings:
        if not _path_exists(compiled_template, secret_path):
            raise ApplicationConfigurationError(
                f"路由 {route.route_id} 破坏了秘密字段路径：{secret_path}"
            )
    for target, source in route.payload_bindings.items():
        overlapping_secret = next(
            (
                secret_path
                for secret_path in profile.secret_bindings
                if _paths_overlap(target, secret_path)
            ),
            None,
        )
        if overlapping_secret:
            raise ApplicationConfigurationError(
                f"路由 {route.route_id} 的 payloadBindings 不允许覆盖秘密字段：{overlapping_secret}"
            )
        _validate_binding_source(source, enabled_fields, route.route_id)
        if not _path_parent_exists(compiled_template, target):
            raise ApplicationConfigurationError(
                f"路由 {route.route_id} 的绑定目标父路径不存在：{target}"
            )
    return FrozenApplicationLinkRoute(
        route_id=route.route_id,
        environment=normalized_environment,
        application_methods=route.application_methods,
        category_code=route.category_code,
        integration_profile_id=profile.id,
        integration_profile_version=profile.version,
        integration_profile_checksum=profile.checksum,
        required_fields=route.required_fields,
        compiled_request_template=compiled_template,
        payload_bindings=route.payload_bindings,
        secret_bindings=profile.secret_bindings,
    )


def validate_catalog_application_link_plans(catalog: Any) -> None:
    route_ids: list[str] = [
        route.route_id
        for product in catalog.products.values()
        for route in product.features.application_links
    ]
    if len(route_ids) != len(set(route_ids)):
        duplicate = next(route_id for route_id in route_ids if route_ids.count(route_id) > 1)
        raise ApplicationConfigurationError(f"申请链接 routeId 重复：{duplicate}")
    for product in catalog.products.values():
        for environment in product.environments:
            for method in product.applicationMethods:
                compile_application_link_plan(
                    catalog=catalog,
                    product_code=product.code,
                    environment=environment,
                    method_code=method.code,
                )


def _validate_binding_source(source: str, enabled_fields: set[str], route_id: str) -> None:
    if source in {"product", "environment", "category", "payload"}:
        return
    field_name = source.removeprefix("payload.") if source.startswith("payload.") else source
    if field_name not in enabled_fields:
        raise ApplicationConfigurationError(
            f"路由 {route_id} 的绑定来源未在当前产品/申请方式启用：{source}"
        )


def _deep_merge(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _deep_merge(current, value)
        else:
            target[key] = deepcopy(value)


def _path_exists(content: Mapping[str, Any], path: str) -> bool:
    current: Any = content
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False
        current = current[part]
    return True


def _path_parent_exists(content: Mapping[str, Any], path: str) -> bool:
    parts = [part for part in path.split(".") if part]
    if not parts:
        return False
    current: Any = content
    for part in parts[:-1]:
        if not isinstance(current, Mapping) or part not in current:
            return False
        current = current[part]
    return isinstance(current, Mapping)


def _paths_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(f"{right}.") or right.startswith(f"{left}.")
