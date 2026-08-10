import json
from pathlib import Path

from apps.utils.http import config


def _copy_examples(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for path in source.glob("*.example.json"):
        destination = target / path.name.replace(".example.json", ".local.json")
        destination.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def _install_split_config(tmp_path, monkeypatch) -> None:
    environments = tmp_path / "environments"
    endpoints = tmp_path / "endpoints"
    runtime = tmp_path / "runtime"
    _copy_examples(config.ENVIRONMENT_CONFIG_DIR, environments)
    _copy_examples(config.ENDPOINT_CONFIG_DIR, endpoints)
    _copy_examples(config.RUNTIME_CONFIG_DIR, runtime)
    monkeypatch.setattr(config, "ENVIRONMENT_CONFIG_DIR", environments)
    monkeypatch.setattr(config, "ENDPOINT_CONFIG_DIR", endpoints)
    monkeypatch.setattr(config, "RUNTIME_CONFIG_DIR", runtime)
    monkeypatch.setattr(config, "LOCAL_ENDPOINT_CONFIG_PATH", endpoints / "endpoints.local.json")
    monkeypatch.setattr(config, "LOCAL_ENVIRONMENT_CONFIG_PATH", runtime / "application.local.json")
    monkeypatch.setattr(config, "IDENTITY_CONFIG_PATH", runtime / "identity.local.json")
    monkeypatch.setattr(
        config,
        "COMPATIBILITY_ENVIRONMENT_CONFIG_PATH",
        tmp_path / "environments.local.json",
    )
    monkeypatch.setattr(
        config,
        "LEGACY_ENVIRONMENT_CONFIG_PATH",
        tmp_path / "legacy-environments.local.json",
    )
    monkeypatch.setattr(
        config,
        "LEGACY_IDENTITY_CONFIG_PATH",
        tmp_path / "legacy-identity.local.json",
    )
    monkeypatch.delenv("CJDK_JYRC_IDENTITY_CONFIG", raising=False)
    config.clear_environment_config_cache()


def test_application_example_loads_from_new_primary_path(tmp_path, monkeypatch) -> None:
    example_path = config.RUNTIME_CONFIG_DIR / "application.example.json"
    example = json.loads(example_path.read_text(encoding="utf-8"))
    assert "secrets" not in example
    _install_split_config(tmp_path, monkeypatch)

    try:
        configured = config.get_cjdk_jyrc_settings()
    finally:
        config.clear_environment_config_cache()

    assert configured.mode == "real"
    assert set(configured.environments) == {"UAT1", "UAT2", "UATC"}
    assert configured.environment("UAT1").agreement_base_url == "http://uat1-host:8090"
    assert configured.environment("UAT1").session_method == "POST"
    assert configured.environment("UAT1").session_url_template == (
        "http://uat1-host:8090/h5main/microservice/"
        "startSceneLoanOpenBankApply.ajax?auth={auth}"
    )


def test_old_environment_filename_remains_compatible(tmp_path, monkeypatch) -> None:
    compatibility_path = tmp_path / "environments.local.json"
    compatibility_path.write_text(
        json.dumps(
            {
                "mode": "real",
                "environments": {"UAT1": {"agreementBaseUrl": "https://compatibility.example"}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        config,
        "LOCAL_ENVIRONMENT_CONFIG_PATH",
        tmp_path / "application.local.json",
    )
    monkeypatch.setattr(config, "COMPATIBILITY_ENVIRONMENT_CONFIG_PATH", compatibility_path)
    monkeypatch.setattr(
        config,
        "LEGACY_ENVIRONMENT_CONFIG_PATH",
        tmp_path / "legacy-environments.local.json",
    )
    config.clear_environment_config_cache()

    try:
        configured = config.get_cjdk_jyrc_settings()
    finally:
        config.clear_environment_config_cache()

    assert configured.environment("UAT1").agreement_base_url == "https://compatibility.example"


def test_identity_split_config_groups_settings_by_environment(tmp_path, monkeypatch) -> None:
    _install_split_config(tmp_path, monkeypatch)
    try:
        configured = config.get_identity_settings("real")
    finally:
        config.clear_environment_config_cache()

    assert set(configured.environments) == {"UAT1", "UAT2", "UATC"}
    assert configured.video_message_name("uatc") == "identity_ali_video_check_uc_v1"
    assert configured.photo_environment("uat1").base_url.startswith("http://photo-uat1-host")
    assert configured.sms_lookup["UAT2"].log_host_paths == ("/logs/uat2/MSCS/MSCS-MICS",)


def test_request_contract_loads_method_and_path_from_endpoint_folder(
    tmp_path, monkeypatch
) -> None:
    _install_split_config(tmp_path, monkeypatch)

    contract = config.request_contract(
        "agreement",
        "queryTemplates",
        operation_id="fallback",
        method="GET",
        path="/fallback",
    )

    assert contract["method"] == "POST"
    assert contract["path"] == "/h5/microservice/queryAgreementTemplateInfoListEA.do"


def test_legacy_identity_layout_is_normalized() -> None:
    configured = config.IdentitySettings.model_validate(
        {
            "endpoints": {"getPublicKey": "/public-key"},
            "videoTemplates": {"UAT1": "video-v1"},
            "photo": {"UAT1": {"baseUrl": "https://photo.example"}},
            "smsLookup": {
                "UAT1": {
                    "url": "https://logs.example",
                    "zone": "uat",
                    "logHostPaths": ["/logs/uat"],
                }
            },
        }
    )

    assert configured.video_message_name("UAT1") == "video-v1"
    assert configured.photo_environment("UAT1").base_url == "https://photo.example"
    assert configured.sms_lookup["UAT1"].url == "https://logs.example"
