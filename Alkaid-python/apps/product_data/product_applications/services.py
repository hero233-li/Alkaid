import json
from typing import Any

from apps.integrations.cjdk_jyrc.config import is_configured_environment
from apps.jobs.models import Job
from apps.product_data.catalog import (
    PRODUCT_ROOT,
    ProductCatalog,
    ProductExecutionSnapshot,
    load_product_catalog,
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

    product = None
    if catalog is not None:
        try:
            product = catalog.product(submission.product)
        except ValueError as exc:
            raise ProductConfigurationError(f"未知产品：{submission.product}") from exc

    payload = submission.payload
    if payload.get("product") not in {None, submission.product}:
        raise ProductConfigurationError("payload.product 与提交产品不一致")
    environment = payload.get("environment")
    if (
        product is not None
        and environment not in product.environments
        and not is_configured_environment(str(environment or ""))
    ):
        raise ProductConfigurationError("当前环境不支持该产品，或未配置对应基础地址")

    customer_type = validate_customer_type(payload)
    if payload.get("applicationMethod") != execution_snapshot.method_code:
        raise ProductConfigurationError("申请方式与 Job 执行配置不一致")
    known_fields = set(execution_snapshot.fields) | INTEGRATION_OPTIONAL_FIELDS
    unknown_fields = set(payload) - known_fields
    if unknown_fields:
        raise ProductConfigurationError(f"提交了未知字段：{', '.join(sorted(unknown_fields))}")
    required_fields = set(execution_snapshot.required_fields)
    missing = [
        name
        for name in required_fields
        if payload.get(name) is None or payload.get(name) == ""
    ]
    if missing:
        raise ProductConfigurationError(f"缺少必填字段：{', '.join(sorted(missing))}")

    project_id = payload.get("projectId")
    cooperation_project_id = payload.get("cooperationProjectId")
    if (
        project_id is not None
        and cooperation_project_id is not None
        and project_id != cooperation_project_id
    ):
        raise ProductConfigurationError("projectId 与 cooperationProjectId 不一致")

    if product is not None:
        _validate_location_hierarchy(product.locations, payload)
    payload["customerType"] = customer_type.value


def validate_customer_type(payload: dict[str, Any]) -> CustomerType:
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
    if company_name:
        payload["companyName"] = company_name
    return customer_type


def resolve_application_link_category(product_code: str, environment: str) -> str:
    """Read the existing product-local applicationLinks route for this environment."""

    for path in sorted(PRODUCT_ROOT.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProductConfigurationError(f"产品配置读取失败：{path.name}: {exc}") from exc
        if raw.get("code") != product_code:
            continue
        routes = (raw.get("features") or {}).get("applicationLinks") or []
        for route in routes:
            if route.get("environment") == environment:
                category = str(route.get("category") or "").strip()
                if category in {"动态链接", "太阳码"}:
                    return category
                raise ProductConfigurationError(
                    f"产品 {product_code} 在环境 {environment} 的申请链接类别无效"
                )
        raise ProductConfigurationError(
            f"产品 {product_code} 在环境 {environment} 未配置申请链接"
        )
    raise ProductConfigurationError(f"未知产品：{product_code}")


def _validate_location_hierarchy(locations: tuple[Any, ...], payload: dict[str, Any]) -> None:
    location = next((item for item in locations if item.value == payload.get("location")), None)
    if location is None:
        raise ProductConfigurationError("地区配置无效")
    branch = next((item for item in location.branches if item.value == payload.get("branch")), None)
    if branch is None:
        raise ProductConfigurationError("机构配置无效")
    if not any(item.value == payload.get("outlet") for item in branch.outlets):
        raise ProductConfigurationError("网点配置无效")


def resolve_product_snapshot(job: Job, product_code: str) -> ProductExecutionSnapshot:
    if job.execution_config_snapshot:
        return ProductExecutionSnapshot.model_validate(job.execution_config_snapshot)
    return load_product_catalog().snapshot(product_code)


def build_product_application_result(
    submission: ProductApplicationSubmission,
    snapshot: ProductExecutionSnapshot,
    *,
    flow_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "validated": True,
        "product": submission.product,
        "productType": snapshot.product_type,
        "customerType": submission.payload["customerType"],
        "switch": snapshot.switch_field,
        "switchEnabled": submission.payload[snapshot.switch_field],
        "executionConfigVersion": snapshot.catalog_version,
        "applicationMethod": snapshot.method_code,
        "executionFields": list(snapshot.fields),
        "message": "产品申请参数校验完成",
        **flow_result,
    }


def run_product_application(
    job: Job,
    submission: ProductApplicationSubmission,
    *,
    snapshot: ProductExecutionSnapshot | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for callers not yet migrated to ProductApplicationFlow."""

    from apps.product_data.product_applications.flow import ProductApplicationFlow

    return ProductApplicationFlow().execute(
        job=job,
        submission=submission,
        snapshot=snapshot,
    )
