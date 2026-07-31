import json

import pytest

from apps.integrations.cjdk_jyrc.java_gateway import (
    JavaApplicationLinkGateway,
)
from apps.integrations.cjdk_jyrc.request_builder import (
    ApplicationLinkRequestError,
    build_application_link_request,
)


def test_product_payload_is_copied_and_bound(tmp_path) -> None:
    product_root = tmp_path / "products"
    product_root.mkdir()

    product_path = product_root / "product.json"
    source = {
        "code": "CJDK-ZHHX",
        "features": {
            "applicationLinks": [
                {
                    "environment": "UAT1",
                    "category": "太阳码",
                    "requiredFields": ["projectId"],
                    "payload": {
                        "REQ_HEAD": {},
                        "REQ_BODY": {
                            "request": {
                                "selbl_prod_id": "",
                                "co_project_id": "",
                            }
                        },
                    },
                    "payloadBindings": {
                        "REQ_BODY.request.selbl_prod_id": "product",
                        "REQ_BODY.request.co_project_id": "projectId",
                    },
                }
            ]
        },
    }
    product_path.write_text(
        json.dumps(source, ensure_ascii=False),
        encoding="utf-8",
    )

    request = build_application_link_request(
        product="CJDK-ZHHX",
        environment="uat1",
        category="太阳码",
        submission_payload={
            "projectId": "PROJECT-001",
        },
        product_root=product_root,
    )

    external = request.external_request()
    assert external["env"] == "UAT1"
    assert external["cooperationProjectId"] == "PROJECT-001"
    request_body = external["payload"]["REQ_BODY"]["request"]
    assert request_body["selbl_prod_id"] == "CJDK-ZHHX"
    assert request_body["co_project_id"] == "PROJECT-001"

    original = json.loads(product_path.read_text(encoding="utf-8"))
    original_body = (
        original["features"]["applicationLinks"][0]
        ["payload"]["REQ_BODY"]["request"]
    )
    assert original_body["selbl_prod_id"] == ""
    assert original_body["co_project_id"] == ""


def test_missing_required_binding_value_is_rejected(tmp_path) -> None:
    product_root = tmp_path / "products"
    product_root.mkdir()
    (product_root / "product.json").write_text(
        json.dumps(
            {
                "code": "P1",
                "features": {
                    "applicationLinks": [
                        {
                            "environment": "UAT1",
                            "category": "太阳码",
                            "requiredFields": ["projectId"],
                            "payload": {},
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ApplicationLinkRequestError,
        match="projectId",
    ):
        build_application_link_request(
            product="P1",
            environment="UAT1",
            category="太阳码",
            submission_payload={},
            product_root=product_root,
        )


def test_java_result_uses_last_alkaid_result_line() -> None:
    result = JavaApplicationLinkGateway._parse_result(
        "SDK log\n"
        'ALKAID_RESULT={"internal_url":"old","external_url":"old"}\n'
        "more log\n"
        'ALKAID_RESULT={"internalUrl":"in","externalUrl":"out"}\n'
    )

    assert result == {
        "internalUrl": "in",
        "externalUrl": "out",
    }


def test_java_result_marker_is_required() -> None:
    with pytest.raises(RuntimeError, match="ALKAID_RESULT"):
        JavaApplicationLinkGateway._parse_result("SDK completed")
