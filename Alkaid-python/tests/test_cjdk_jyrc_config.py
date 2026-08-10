import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.utils.http import config
from apps.utils.java.application_link import execute_java
from apps.workflow.product_applications import cjdk


def test_package_import_does_not_monkey_patch_config_functions() -> None:
    original = config.get_cjdk_jyrc_settings
    importlib.reload(cjdk)
    assert config.get_cjdk_jyrc_settings is original


def test_second_java_runtime_module_has_been_removed() -> None:
    runtime_path = Path(config.__file__).with_name("java_runtime.py")
    assert not runtime_path.exists()


def test_java_gateway_uses_local_environment_gateway_settings(tmp_path, monkeypatch) -> None:
    sdk_dir = tmp_path / "sdk"
    (sdk_dir / "lib").mkdir(parents=True)
    java = tmp_path / "jdk" / "java.exe"
    java.parent.mkdir()
    java.write_text("", encoding="utf-8")
    jar = sdk_dir / "link.jar"
    jar.write_text("", encoding="utf-8")
    local_path = tmp_path / "environments.local.json"
    local_path.write_text(
        json.dumps(
            {
                "mode": "real",
                "applicationLinkUrlMode": "internal",
                "javaGateway": {
                    "sdkDir": str(sdk_dir),
                    "javaExecutable": str(java),
                    "jar": "link.jar",
                    "mainClass": "local.Main",
                    "outputEncoding": "utf-8",
                    "timeoutSeconds": 7,
                },
                "environments": {"UAT1": {"agreementBaseUrl": "http://agreement.local"}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "LOCAL_ENVIRONMENT_CONFIG_PATH", local_path)
    config.clear_environment_config_cache()
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        return SimpleNamespace(
            returncode=0,
            stdout='ALKAID_RESULT={"internal_url":"in","external_url":"out"}',
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    try:
        execute_java({"env": "UAT1"})
    finally:
        config.clear_environment_config_cache()

    assert captured["command"][0] == str(java)
    assert captured["command"][3] == "local.Main"
    assert captured["kwargs"]["cwd"] == str(sdk_dir)
    assert captured["kwargs"]["timeout"] == 7


def test_real_readiness_lists_missing_start_apply_contract(tmp_path, monkeypatch) -> None:
    sdk_dir = tmp_path / "sdk"
    sdk_dir.mkdir()
    java = sdk_dir / "java"
    java.write_text("", encoding="utf-8")
    jar = sdk_dir / "application-link.jar"
    jar.write_text("", encoding="utf-8")
    configured = config.CjdkJyrcSettings(
        mode="real",
        application_link_url_mode="internal",
        sdk_dir=sdk_dir,
        java_executable=java,
        jar=jar,
        main_class="example.Main",
        environments={
            "UAT1": config.EnvironmentSettings(agreement_base_url="https://agreement.test")
        },
    )
    monkeypatch.setattr(config, "get_cjdk_jyrc_settings", lambda: configured)
    monkeypatch.setattr(
        config,
        "get_identity_settings",
        lambda mode: config._mock_identity_settings(),
    )

    with pytest.raises(ImproperlyConfigured) as error:
        config.validate_cjdk_jyrc_readiness({"UAT1"})

    assert "startApply 接口路径" in str(error.value)
    assert "startApply 原始报文模板" in str(error.value)
