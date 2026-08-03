from __future__ import annotations

from copy import deepcopy

from apps.product_data.catalog import ProductExecutionSnapshot
from apps.product_data.product_applications.contracts import (
    ApplicationLinkCommand,
    ApplicationLinkGateway,
    ApplicationLinkKind,
    ExternalSessionGateway,
    ProgressReporter,
    SessionStatus,
)
from apps.product_data.product_applications.results import ApplicationSessionOutcome


def generate_application_link_and_establish_session(
    *,
    application_links: ApplicationLinkGateway,
    external_session: ExternalSessionGateway,
    snapshot: ProductExecutionSnapshot,
    application_link_kind: ApplicationLinkKind,
    progress: ProgressReporter | None = None,
) -> ApplicationSessionOutcome:
    route = snapshot.application_link_route
    links = application_links.generate_application_link(
        ApplicationLinkCommand(
            plan=route.model_dump(mode="json"),
            normalized_payload=deepcopy(snapshot.normalized_payload),
        )
    )
    _report(progress, "application_link", 40, "申请链接获取完成")
    application_url = (
        links.internal_url if application_link_kind == "internal" else links.external_url
    )
    session = external_session.initialize_session(application_url)
    if session.status != SessionStatus.ESTABLISHED:
        raise RuntimeError(
            "外系统 Session 未满足配置要求，停止协议查询；"
            f"当前状态={session.status.value}；"
            f"缺少 Cookie={list(session.missing_cookies)}；"
            f"缺少 Header={list(session.missing_headers)}；"
            f"任一 Header 要求={list(session.missing_any_headers)}"
        )
    _report(progress, "session", 50, "申请页面 Session 建立完成")
    return ApplicationSessionOutcome(
        application_link_category=route.category_code.display_name,
        application_links=links,
        selected_application_link_kind=application_link_kind,
        session=session,
    )


def _report(reporter: ProgressReporter | None, stage: str, progress: int, message: str) -> None:
    if reporter is not None:
        reporter(stage=stage, progress=progress, message=message)
