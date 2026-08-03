import re
from collections.abc import Mapping
from copy import deepcopy
from decimal import Decimal
from typing import Any

from apps.product_data.catalog import (
    CatalogField,
    ProductCatalog,
    ProductCatalogSource,
    ProductExecutionSnapshot,
)
from apps.product_data.product_applications.schemas import (
    CustomerType,
    ProductApplicationSubmission,
)


class ProductConfigurationError(ValueError):
    pass


INTEGRATION_OPTIONAL_FIELDS = {
    "idType",
    "projectId",
    "cooperationProjectId",
}


def validate_submission(
    submission: ProductApplicationSubmission,
    execution_snapshot: ProductExecutionSnapshot,
    catalog: ProductCatalog | None = None,
) -> None:
    if execution_snapshot.product_code != submission.product:
        raise ProductConfigurationError("Job 执行配置与提交产品不一致")

    payload = submission.payload
    if payload.get("product") not in {None, submission.product}:
        raise ProductConfigurationError("payload.product 与提交产品不一致")
    environment = str(payload.get("environment") or "").strip().upper()
    if environment != execution_snapshot.environment:
        raise ProductConfigurationError("环境与 Job 执行配置不一致")

    customer_type = validate_customer_type(payload)
    if payload.get("applicationMethod") != execution_snapshot.method_code:
        raise ProductConfigurationError("申请方式与 Job 执行配置不一致")
    known_fields = set(execution_snapshot.fields) | INTEGRATION_OPTIONAL_FIELDS
    unknown_fields = set(payload) - known_fields
    if unknown_fields:
        raise ProductConfigurationError(f"提交了未知字段：{', '.join(sorted(unknown_fields))}")
    required_fields = set(execution_snapshot.required_fields)
    missing = [
        name for name in required_fields if payload.get(name) is None or payload.get(name) == ""
    ]
    if missing:
        raise ProductConfigurationError(f"缺少必填字段：{', '.join(sorted(missing))}")

    if catalog is not None:
        try:
            product = catalog.product(submission.product)
        except ValueError as exc:
            raise ProductConfigurationError(f"未知产品：{submission.product}") from exc
        if environment not in product.environments:
            raise ProductConfigurationError("当前环境不支持该产品")
        if payload.get("cooperationProjectId") != product.cooperationProjectId:
            raise ProductConfigurationError("合作项目与产品配置不一致")
        _validate_location_hierarchy(product.locations, payload)
    if payload.get("customerType") != customer_type.value:
        raise ProductConfigurationError("customerType 标准化结果不一致")


def normalize_environment(value: object, catalog: ProductCatalog) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductConfigurationError("环境不能为空")

    normalized = value.strip().upper()
    for option in catalog.reference.environments:
        if normalized in {option.value.upper(), option.label.upper()}:
            return option.value

    allowed = ", ".join(option.value for option in catalog.reference.environments)
    raise ProductConfigurationError(f"环境必须是以下值之一：{allowed}")


def validate_customer_type(payload: Mapping[str, Any]) -> CustomerType:
    if "legalPerson" in payload:
        raise ProductConfigurationError("legalPerson 布尔字段已停用，请提交 customerType")
    try:
        customer_type = CustomerType(payload.get("customerType"))
    except (TypeError, ValueError):
        allowed = ", ".join(item.value for item in CustomerType)
        raise ProductConfigurationError(f"customerType 必须是以下值之一：{allowed}") from None

    company_value = payload.get("companyName")
    if company_value is not None and not isinstance(company_value, str):
        raise ProductConfigurationError("企业名称必须是字符串")
    company_name = (company_value or "").strip()
    if customer_type in {CustomerType.LEGAL_PERSON, CustomerType.SHAREHOLDER} and not company_name:
        raise ProductConfigurationError("法人或股东类型必须填写企业名称")
    if customer_type == CustomerType.FARMER and company_name:
        raise ProductConfigurationError("填写企业名称后，客户类型必须是法人或股东")
    return customer_type


def validate_customer_rules(payload: Mapping[str, Any]) -> None:
    validate_customer_type(payload)


def validate_and_normalize_payload(
    *,
    product: ProductCatalogSource,
    method_code: str,
    raw_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Strictly validate declared product fields without mutating caller data."""

    normalized = deepcopy(dict(raw_payload))
    fields = product.enabled_execution_fields(method_code)
    for field in fields:
        name = field.name
        if name not in raw_payload:
            if field.required_for(method_code):
                raise ProductConfigurationError(f"缺少必填字段：{name}")
            continue
        value = raw_payload[name]
        if value is None:
            if field.required_for(method_code) or not field.nullable:
                raise ProductConfigurationError(f"字段 {name} 不能为空")
            normalized[name] = None
            continue
        value = _strict_field_value(field, value)
        if field.required_for(method_code) and value == "":
            raise ProductConfigurationError(f"缺少必填字段：{name}")
        _validate_field_constraints(field, value)
        normalized[name] = value
    return normalized


def validate_location_hierarchy(locations: tuple[Any, ...], payload: Mapping[str, Any]) -> None:
    _validate_location_hierarchy(locations, payload)


def _strict_field_value(field: CatalogField, value: Any) -> Any:
    name = field.name
    expected = field.valueType
    actual = type(value).__name__
    if expected in {"string", "enum"}:
        if not isinstance(value, str):
            raise ProductConfigurationError(f"字段 {name} 类型错误：期望 {expected}，实际 {actual}")
        return value.strip() if field.strip else value
    if expected == "boolean":
        if type(value) is not bool:
            raise ProductConfigurationError(f"字段 {name} 类型错误：期望 boolean，实际 {actual}")
        return value
    if expected == "integer":
        if type(value) is not int:
            raise ProductConfigurationError(f"字段 {name} 类型错误：期望 integer，实际 {actual}")
        return value
    if expected == "decimal":
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ProductConfigurationError(f"字段 {name} 类型错误：期望 decimal，实际 {actual}")
        return value
    raise ProductConfigurationError(f"字段 {name} valueType 无效：{expected}")


def _validate_field_constraints(field: CatalogField, value: Any) -> None:
    name = field.name
    if isinstance(value, str):
        if field.minLength is not None and len(value) < field.minLength:
            raise ProductConfigurationError(f"字段 {name} 长度不能小于 {field.minLength}")
        if field.maxLength is not None and len(value) > field.maxLength:
            raise ProductConfigurationError(f"字段 {name} 长度不能超过 {field.maxLength}")
        if field.pattern and re.fullmatch(field.pattern, value) is None:
            raise ProductConfigurationError(f"字段 {name} 格式不符合 pattern")
    if field.allowedValues and not any(
        type(value) is type(allowed) and value == allowed for allowed in field.allowedValues
    ):
        raise ProductConfigurationError(f"字段 {name} 必须是 allowedValues 中的值")
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        if field.minimum is not None and value < field.minimum:
            raise ProductConfigurationError(f"字段 {name} 不能小于 {field.minimum}")
        if field.maximum is not None and value > field.maximum:
            raise ProductConfigurationError(f"字段 {name} 不能大于 {field.maximum}")


def _validate_location_hierarchy(locations: tuple[Any, ...], payload: Mapping[str, Any]) -> None:
    location = next((item for item in locations if item.value == payload.get("location")), None)
    if location is None:
        raise ProductConfigurationError("地区配置无效")
    branch = next((item for item in location.branches if item.value == payload.get("branch")), None)
    if branch is None:
        raise ProductConfigurationError("机构配置无效")
    if not any(item.value == payload.get("outlet") for item in branch.outlets):
        raise ProductConfigurationError("网点配置无效")
