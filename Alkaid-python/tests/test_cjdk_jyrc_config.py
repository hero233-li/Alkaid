import importlib
import json
from pathlib import Path
from types import SimpleNamespace

from apps.integrations import cjdk_jyrc
from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.java_gateway import JavaApplicationLinkGateway


def test_package_import_does_not_monkey_patch_config_functions() -> None:
    original = config.java_sdk_dir
    importlib.reload(cjdk_jyrc)
    assert config.java_sdk_dir is original


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
    gateway = object.__new__(JavaApplicationLinkGateway)
    gateway._write_diagnostic = lambda *args, **kwargs: None
    try:
        gateway._execute_java({"env": "UAT1"})
    finally:
        config.clear_environment_config_cache()

    assert captured["command"][0] == str(java)
    assert captured["command"][3] == "local.Main"
    assert captured["kwargs"]["cwd"] == str(sdk_dir)
    assert captured["kwargs"]["timeout"] == 7
