import pytest

from apps.integrations.cjdk_jyrc.client import evaluate_session_state
from apps.integrations.cjdk_jyrc.config import SessionRequirement, UrlPolicy
from apps.integrations.cjdk_jyrc.url_policy import (
    UnsafeExternalUrl,
    may_forward_session_headers,
    validate_external_url,
)
from apps.product_data.catalog import load_product_catalog
from apps.product_data.product_applications.contracts import ApplicationLinksResult, SessionStatus
from apps.product_data.product_applications.preparation import freeze_product_execution_snapshot
from apps.product_data.product_applications.schemas import ProductApplicationSubmission
from apps.product_data.product_applications.use_cases import execute_product_application

REQUIREMENT = SessionRequirement(
    requiredCookies=("JSESSIONID", "token_id"),
    requiredAnyHeaders=("X-Token", "X-FCOS-SESSIONID"),
)


def test_page_open_and_arbitrary_cookie_do_not_establish_session() -> None:
    opened = evaluate_session_state(
        page_opened=True, cookie_names=(), header_names=(), requirement=REQUIREMENT
    )
    partial = evaluate_session_state(
        page_opened=True,
        cookie_names=("unrelated",),
        header_names=(),
        requirement=REQUIREMENT,
    )
    assert opened.status == SessionStatus.PAGE_OPENED
    assert partial.status == SessionStatus.PARTIAL


def test_session_is_established_only_when_requirements_are_met() -> None:
    state = evaluate_session_state(
        page_opened=True,
        cookie_names=("JSESSIONID", "token_id"),
        header_names=("X-Token",),
        requirement=REQUIREMENT,
    )
    assert state.status == SessionStatus.ESTABLISHED


def _policy(**updates) -> UrlPolicy:
    values = {
        "allowedSchemes": ["http"],
        "allowedHosts": ["12.244.142.116", "allowed.internal"],
        "allowedPorts": [8090],
        "allowCrossHostRedirect": False,
        "forwardSessionHeadersToHosts": ["12.244.142.116"],
    }
    values.update(updates)
    return UrlPolicy.model_validate(values)


def test_url_policy_checks_scheme_credentials_host_port_and_redirects() -> None:
    policy = _policy()
    assert validate_external_url("http://12.244.142.116:8090/path", policy)
    for url in (
        "https://12.244.142.116:8090/path",
        "http://user:pass@12.244.142.116:8090/path",
        "http://unknown.internal:8090/path",
        "http://12.244.142.116:8080/path",
    ):
        with pytest.raises(UnsafeExternalUrl):
            validate_external_url(url, policy)
    with pytest.raises(UnsafeExternalUrl, match="不同 host"):
        validate_external_url(
            "http://allowed.internal:8090/next",
            policy,
            previous_url="http://12.244.142.116:8090/start",
        )
    cross_host = _policy(allowCrossHostRedirect=True)
    assert validate_external_url(
        "http://allowed.internal:8090/next",
        cross_host,
        previous_url="http://12.244.142.116:8090/start",
    )


def test_session_headers_only_forward_to_explicit_hosts() -> None:
    policy = _policy()
    assert may_forward_session_headers("http://12.244.142.116:8090/path", policy)
    assert not may_forward_session_headers("http://allowed.internal:8090/path", policy)


def test_partial_session_stops_before_agreement_query() -> None:
    submission = ProductApplicationSubmission(
        name="产品B申请",
        product="product-b",
        payload={
            "environment": "UAT1",
            "product": "product-b",
            "location": "example-location",
            "branch": "example-branch",
            "outlet": "example-outlet",
            "cooperationProjectId": "PROJECT-002",
            "personName": "测试用户",
            "certificateNo": "330101199001011234",
            "cardNo": "6222000000000000",
            "phone": "13800138000",
            "customerType": "farmer",
            "applicationMethod": "normal",
            "redShieldEnabled": True,
        },
    )
    prepared = freeze_product_execution_snapshot(submission, load_product_catalog())

    class PartialPort:
        application_link_url_mode = "internal"
        queried = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def generate_application_link(self, command):
            return ApplicationLinksResult(
                internal_url="http://allowed/link", external_url="http://allowed/link"
            )

        def initialize_session(self, application_url):
            return evaluate_session_state(
                page_opened=True,
                cookie_names=("unrelated",),
                header_names=(),
                requirement=REQUIREMENT,
            )

        def query_agreement_templates(self, payload):
            self.queried = True
            return ()

    port = PartialPort()
    with pytest.raises(RuntimeError, match="停止协议查询"):
        execute_product_application(
            runtime=port,
            application_links=port,
            external_session=port,
            agreements=port,
            submission=prepared.submission,
            snapshot=prepared.snapshot,
            application_link_kind="internal",
        )
    assert port.queried is False
