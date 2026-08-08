import pytest

from apps.product_applications.api import ProductApplicationSubmission
from apps.product_applications.cjdk.config import EnvironmentSettings
from apps.product_applications.cjdk.runtime import (
    SessionStatus,
    UnsafeExternalUrl,
    compile_application_link_plan,
    evaluate_session_state,
    may_forward_session_headers,
    validate_external_url,
)
from apps.product_applications.workflow import (
    execute_product_application,
    freeze_product_execution_snapshot,
)
from apps.product_data.catalog import load_product_catalog

REQUIREMENT = EnvironmentSettings(
    agreement_base_url="http://12.244.142.116:8090",
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


def _policy(**updates) -> EnvironmentSettings:
    values = {
        "agreement_base_url": "http://12.244.142.116:8090",
        "allowedSchemes": ["http"],
        "allowedHosts": ["12.244.142.116", "allowed.internal"],
        "allowedPorts": [8090],
        "allowCrossHostRedirect": False,
        "forwardSessionHeadersToHosts": ["12.244.142.116"],
    }
    values.update(updates)
    return EnvironmentSettings.model_validate(values)


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
    prepared = freeze_product_execution_snapshot(
        submission,
        load_product_catalog(),
        plan_compiler=compile_application_link_plan,
    )

    class PartialPort:
        application_link_url_mode = "internal"
        queried = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def open_application(self, **kwargs):
            state = evaluate_session_state(
                page_opened=True,
                cookie_names=("unrelated",),
                header_names=(),
                requirement=REQUIREMENT,
            )
            if state.status != SessionStatus.ESTABLISHED:
                raise RuntimeError("停止协议查询")
            return {}

        def read_agreements(self, **kwargs):
            self.queried = True
            return {}

    port = PartialPort()
    with pytest.raises(RuntimeError, match="停止协议查询"):
        execute_product_application(
            runtime=port,
            submission=prepared[0],
            snapshot=prepared[1],
            application_link_kind="internal",
        )
    assert port.queried is False
