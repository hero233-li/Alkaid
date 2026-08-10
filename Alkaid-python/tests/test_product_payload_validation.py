from copy import deepcopy

import pytest

from apps.utils.application_links import compile_application_link_plan
from apps.utils.product_Conf.catalog import CatalogField, load_product_catalog
from apps.workflow.product_applications.api import (
    ProductApplicationSubmission,
    ProductConfigurationError,
)
from apps.workflow.product_applications.validation import validate_and_normalize_payload
from apps.workflow.product_applications.workflow import freeze_product_execution_snapshot


def _product_with(field: CatalogField):
    product = load_product_catalog().product("product-b")
    return product.model_copy(update={"fields": (field,)})


@pytest.mark.parametrize("value", [123, ["wrong"], {"value": "wrong"}])
def test_string_rejects_non_string(value) -> None:
    field = CatalogField(name="personName", valueType="string", execution=True)
    with pytest.raises(ProductConfigurationError, match="personName.*期望 string"):
        validate_and_normalize_payload(
            product=_product_with(field), method_code="normal", raw_payload={"personName": value}
        )


@pytest.mark.parametrize("value", ["true", 1])
def test_boolean_rejects_coercion(value) -> None:
    field = CatalogField(name="enabled", valueType="boolean")
    with pytest.raises(ProductConfigurationError, match="enabled.*期望 boolean"):
        validate_and_normalize_payload(
            product=_product_with(field), method_code="normal", raw_payload={"enabled": value}
        )


@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_integer_rejects_bool_float_and_string(value) -> None:
    field = CatalogField(name="term", valueType="integer")
    with pytest.raises(ProductConfigurationError, match="term.*期望 integer"):
        validate_and_normalize_payload(
            product=_product_with(field), method_code="normal", raw_payload={"term": value}
        )


def test_constraints_strip_nullable_required_and_input_immutability() -> None:
    raw = {"name": "  AB12  ", "optional": None}
    before = deepcopy(raw)
    product = (
        load_product_catalog()
        .product("product-b")
        .model_copy(
            update={
                "fields": (
                    CatalogField(
                        name="name",
                        valueType="string",
                        strip=True,
                        minLength=2,
                        maxLength=4,
                        pattern="^[A-Z0-9]+$",
                        requiredFor=("*",),
                    ),
                    CatalogField(name="optional", nullable=True),
                )
            }
        )
    )
    normalized = validate_and_normalize_payload(
        product=product, method_code="normal", raw_payload=raw
    )
    assert normalized == {"name": "AB12", "optional": None}
    assert raw == before


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (CatalogField(name="name", maxLength=2), "ABC", "name.*长度不能超过"),
        (CatalogField(name="code", pattern="^[0-9]+$"), "ABC", "code.*pattern"),
        (
            CatalogField(name="kind", valueType="enum", allowedValues=("A", "B")),
            "C",
            "kind.*allowedValues",
        ),
    ],
)
def test_length_pattern_and_enum_errors_include_field(field, value, message) -> None:
    with pytest.raises(ProductConfigurationError, match=message):
        validate_and_normalize_payload(
            product=_product_with(field), method_code="normal", raw_payload={field.name: value}
        )


def test_required_for_rejects_missing_and_strip_can_be_disabled() -> None:
    required = CatalogField(name="required", requiredFor=("normal",))
    with pytest.raises(ProductConfigurationError, match="required"):
        validate_and_normalize_payload(
            product=_product_with(required), method_code="normal", raw_payload={}
        )
    unstripped = CatalogField(name="raw", strip=False)
    assert (
        validate_and_normalize_payload(
            product=_product_with(unstripped), method_code="normal", raw_payload={"raw": " x "}
        )["raw"]
        == " x "
    )


def test_product_cooperation_project_is_injected_and_conflicts_are_rejected() -> None:
    catalog = load_product_catalog()
    payload = {
        "environment": "UAT1",
        "product": "product-b",
        "location": "example-location",
        "branch": "example-branch",
        "outlet": "example-outlet",
        "personName": "测试用户",
        "certificateNo": "330101199001011234",
        "cardNo": "6222000000000000",
        "phone": "13800138000",
        "customerType": "farmer",
        "applicationMethod": "normal",
        "redShieldEnabled": True,
    }
    prepared = freeze_product_execution_snapshot(
        ProductApplicationSubmission(name="产品B申请", product="product-b", payload=payload),
        catalog,
        plan_compiler=compile_application_link_plan,
    )
    assert prepared[0].payload["cooperationProjectId"] == "PROJECT-002"

    conflicting = {**payload, "cooperationProjectId": "PROJECT-001"}
    with pytest.raises(ProductConfigurationError, match="合作项目与产品配置不一致"):
        freeze_product_execution_snapshot(
            ProductApplicationSubmission(
                name="产品B申请", product="product-b", payload=conflicting
            ),
            catalog,
            plan_compiler=compile_application_link_plan,
        )
