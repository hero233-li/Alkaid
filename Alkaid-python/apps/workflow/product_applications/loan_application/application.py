from collections.abc import Callable, Mapping
from typing import Any, Literal

from apps.utils.http import config
from apps.utils.http.contracts import IntegrationObserver
from apps.utils.java.application_link import generate_application_link
from apps.utils.product_Conf.catalog import ProductExecutionSnapshot
from apps.workflow.product_applications.cjdk.mock import mock_submit_application
from apps.workflow.product_applications.common.agreement import read_agreements
from apps.workflow.product_applications.contracts import SubmittedApplication

ApplicationLinkKind = Literal["internal", "external"]
ProgressReporter = Callable[..., None]


def execute_application(
    *,
    client: Any,
    settings: config.CjdkJyrcSettings,
    observer: IntegrationObserver,
    trace_id: str,
    snapshot: ProductExecutionSnapshot,
    payload: Mapping[str, Any],
    application_link_kind: ApplicationLinkKind,
    progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    application = open_application(
        client=client,
        observer=observer,
        trace_id=trace_id,
        snapshot=snapshot,
        application_link_kind=application_link_kind,
        progress=progress,
    )
    agreements = read_agreements(
        client=client,
        settings=settings,
        payload=payload,
        progress=progress,
    )
    submission = submit_application(settings=settings, payload=payload, progress=progress)
    return {
        **application,
        **agreements,
        "submittedApplication": submission,
    }


def open_application(
    *,
    client: Any,
    observer: IntegrationObserver,
    trace_id: str,
    snapshot: ProductExecutionSnapshot,
    application_link_kind: ApplicationLinkKind,
    progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    links = generate_application_link(
        plan=snapshot.application_link_route,
        normalized_payload=snapshot.normalized_payload,
        observer=observer,
        trace_id=trace_id,
    )
    _report(progress, "application_link", 40, "申请链接获取完成")
    application_url = links[f"{application_link_kind}_url"]
    session = client.acquire_session(application_url)
    if session.status.value != "established":
        raise RuntimeError(f"申请页面 Session 建立失败：{session.status.value}")
    _report(progress, "session", 50, "申请页面 Session 建立完成")
    return {
        "applicationLinkCategory": snapshot.application_link_route.category_code.display_name,
        "selectedApplicationLinkKind": application_link_kind,
        "session": session,
    }


def submit_application(
    *,
    settings: config.CjdkJyrcSettings,
    payload: Mapping[str, Any],
    progress: ProgressReporter | None = None,
) -> SubmittedApplication:
    if settings.mode == "mock":
        application_id, encrypted_name, encrypted_identity_no = mock_submit_application(payload)
        _report(progress, "application_submit", 90, "申请提交完成")
        return SubmittedApplication(
            application_id=application_id,
            encrypted_customer_name=encrypted_name,
            encrypted_identity_no=encrypted_identity_no,
        )
    raise RuntimeError(
        "真实模式缺少 startApply 接口路径和原始报文模板；请补齐 CJDK 配置后再启用真实产品申请"
    )


def _report(reporter: ProgressReporter | None, stage: str, progress: int, message: str) -> None:
    if reporter is not None:
        reporter(stage=stage, progress=progress, message=message)
