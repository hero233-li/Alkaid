import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.utils.application_links import (
    ApplicationConfigurationError,
    compile_application_link_plan,
    load_integration_profile,
)
from apps.utils.http import config
from apps.utils.java.application_link import (
    build_application_link_request,
    execute_java,
)
from apps.utils.java.java_gateway import parse_java_result
from apps.utils.product_Conf.catalog import load_product_catalog


class TestSecretResolver:
    values = {
        "cjdkJyrc.applicationLink.appId": "APP-ID",
        "cjdkJyrc.applicationLink.privateKey": "PRIVATE-KEY",
        "cjdkJyrc.applicationLink.publicKey": "PUBLIC-KEY",
    }

    def resolve(self, reference: str) -> str:
        return self.values[reference]


def _cjdk_catalog_and_plan():
    catalog = load_product_catalog()
    source = catalog.product("product-b")
    product = source.model_copy(update={"code": "CJDK-ZHHX"})
    copied_catalog = catalog.model_copy(update={"products": {"CJDK-ZHHX": product}})
    plan = compile_application_link_plan(
        catalog=copied_catalog,
        product_code="CJDK-ZHHX",
        environment="UAT1",
        method_code="normal",
    )
    return product, plan


def test_product_payload_is_copied_bound_and_secret_injected() -> None:
    product, plan = _cjdk_catalog_and_plan()
    profile_before = deepcopy(load_integration_profile("cjdk-jyrc.application-link", 1).template)
    route_before = deepcopy(product.features.application_links[0].request_template)

    request = build_application_link_request(
        plan=plan,
        normalized_payload={
            "product": "CJDK-ZHHX",
            "environment": "UAT1",
            "cooperationProjectId": "PROJECT-001",
        },
        secret_resolver=TestSecretResolver(),
    )

    external = request
    assert external["env"] == "UAT1"
    assert external["product"] == "CJDK-ZHHX"
    assert external["category"] == "太阳码"
    assert external["cooperationProjectId"] == "PROJECT-001"
    assert external["payload"]["REQ_BODY"]["request"] == {
        "order_no": "XCXYXM_CJDK_JYRC",
        "cooperator_id": "XCXYXM",
        "cooperator_name": "小程序渠道码",
        "loan_flow_stag": "1",
        "selbl_prod_id": "CJDK-ZHHX",
        "co_project_id": "PROJECT-001",
        "appl_chnl_cd": "5C",
    }
    assert external["payload"]["REQ_BODY"]["appId"] == "APP-ID"
    assert external["payload"]["REQ_BODY"]["myPrivateKey"] == "PRIVATE-KEY"
    assert external["payload"]["REQ_BODY"]["apigwPublicKey"] == "PUBLIC-KEY"
    assert load_integration_profile("cjdk-jyrc.application-link", 1).template == profile_before
    assert product.features.application_links[0].request_template == route_before


def test_missing_required_binding_value_is_rejected() -> None:
    _, plan = _cjdk_catalog_and_plan()
    with pytest.raises(ApplicationConfigurationError, match="cooperationProjectId"):
        build_application_link_request(
            plan=plan,
            normalized_payload={"product": "CJDK-ZHHX", "environment": "UAT1"},
            secret_resolver=TestSecretResolver(),
        )


def test_java_gateway_preserves_request_file_contract(tmp_path, monkeypatch) -> None:
    sdk_dir = tmp_path / "sdk"
    lib_dir = sdk_dir / "lib"
    lib_dir.mkdir(parents=True)
    java = tmp_path / "jdk" / "bin" / "java.exe"
    java.parent.mkdir(parents=True)
    java.write_text("", encoding="utf-8")
    jar = sdk_dir / "application-link.jar"
    jar.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    configured = config.CjdkJyrcSettings(
        mode="real",
        application_link_url_mode="internal",
        sdk_dir=sdk_dir,
        java_executable=java,
        jar=Path("application-link.jar"),
        main_class="com.example.ApplicationLinkMain",
        output_encoding="gbk",
        timeout_seconds=15,
        environments={"UAT1": config.EnvironmentSettings(agreement_base_url="http://agreement")},
    )
    monkeypatch.setattr(config, "get_cjdk_jyrc_settings", lambda: configured)

    def fake_run(command, **kwargs):
        request_path = Path(command[-1])
        captured.update(
            command=command,
            kwargs=kwargs,
            request=json.loads(request_path.read_text(encoding="utf-8")),
        )
        return SimpleNamespace(
            returncode=0,
            stdout='ALKAID_RESULT={"internal_url":"in","external_url":"out"}\n',
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    result = execute_java({"env": "UAT1", "payload": {"中文": "值"}})

    command = captured["command"]
    kwargs = captured["kwargs"]
    assert command[0] == str(java)
    assert command[1] == "-cp"
    assert command[3] == "com.example.ApplicationLinkMain"
    assert len(command[4:]) == 1
    assert kwargs["cwd"] == str(sdk_dir)
    assert kwargs["encoding"] == "gbk"
    assert kwargs["timeout"] == 15
    assert captured["request"] == {"env": "UAT1", "payload": {"中文": "值"}}
    assert result == {"internal_url": "in", "external_url": "out"}


def test_java_result_uses_last_alkaid_result_line() -> None:
    result = parse_java_result(
        "SDK log\n"
        'ALKAID_RESULT={"internal_url":"old","external_url":"old"}\n'
        "more log\n"
        'ALKAID_RESULT={"internalUrl":"in","externalUrl":"out"}\n'
    )
    assert result == {"internalUrl": "in", "externalUrl": "out"}


def test_java_result_marker_is_required() -> None:
    with pytest.raises(RuntimeError, match="ALKAID_RESULT"):
        parse_java_result("SDK completed")
