import json
from pathlib import Path
from typing import Any

from apps.jobs.models import Job
from apps.product_data.execution_config import (
    ProductExecutionSnapshot,
    load_execution_catalog,
)
from apps.product_data.handlers import get_product_handler
from apps.product_data.schemas import (
    CustomerType,
    ProductApplicationConfig,
    ProductApplicationSubmission,
)

CONFIG_PATH = Path(__file__).with_name("configs") / "product_application.json"


class ProductConfigurationError(ValueError):
    pass


def load_product_application_config() -> ProductApplicationConfig:
    try:
        content = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return ProductApplicationConfig.model_validate(content)
    except (OSError, ValueError) as exc:
        raise ProductConfigurationError(f"产品申请配置无效：{exc}") from exc


def validate_submission(
    submission: ProductApplicationSubmission,
    config: ProductApplicationConfig | None = None,
    execution_snapshot: ProductExecutionSnapshot | None = None,
) -> None:
    current = config or load_product_application_config()
    product = next((item for item in current.products if item.value == submission.product), None)
    if product is None:
        raise ProductConfigurationError(f"未知产品：{submission.product}")

    payload = submission.payload
    if payload.get("product") not in {None, submission.product}:
        raise ProductConfigurationError("payload.product 与提交产品不一致")
    environment = payload.get("environment")
    if environment not in product.environments:
        raise ProductConfigurationError("当前环境不支持该产品")

    customer_type = validate_customer_type(payload)
    active_field_names = current.field_names_for(product)
    active_fields = [field for field in current.fields if field.name in active_field_names]
    known_fields = {field.name for field in active_fields if field.submit}
    known_fields.add("customerType")
    execution_required: set[str] = set()
    if execution_snapshot:
        known_fields.add("applicationMethod")
        if payload.get("applicationMethod") != execution_snapshot.method_code:
            raise ProductConfigurationError("申请方式与 Job 执行配置不一致")
        for field_name, field in execution_snapshot.field_definitions.items():
            source_name = field.source.rsplit(".", 1)[-1]
            known_fields.add(source_name)
            if field_name in execution_snapshot.required_fields:
                execution_required.add(source_name)
    unknown_fields = set(payload) - known_fields
    if unknown_fields:
        raise ProductConfigurationError(f"提交了未知字段：{', '.join(sorted(unknown_fields))}")
    required_fields = {field.name for field in active_fields if field.required}
    required_fields.update(product.requiredFields)
    required_fields.update(execution_required)
    missing = [
        name for name in required_fields if payload.get(name) is None or payload.get(name) == ""
    ]
    if missing:
        raise ProductConfigurationError(f"缺少必填字段：{', '.join(sorted(missing))}")

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


def _validate_location_hierarchy(locations: tuple[Any, ...], payload: dict[str, Any]) -> None:
    location = next((item for item in locations if item.value == payload.get("location")), None)
    if location is None:
        raise ProductConfigurationError("地区配置无效")
    branch = next((item for item in location.branches if item.value == payload.get("branch")), None)
    if branch is None:
        raise ProductConfigurationError("机构配置无效")
    if not any(item.value == payload.get("outlet") for item in branch.outlets):
        raise ProductConfigurationError("网点配置无效")


class ProductApplicationExecutor:
    def execute(
        self,
        job: Job,
        submission: ProductApplicationSubmission,
        *,
        snapshot: ProductExecutionSnapshot | None = None,
    ) -> dict[str, Any]:
        snapshot = snapshot or self.resolve_snapshot(job, submission.product)
        if snapshot.product_code != submission.product:
            raise ProductConfigurationError("Job 执行配置与提交产品不一致")
        handler_result = get_product_handler(snapshot.handler).execute(job, submission)
        return {
            "validated": True,
            "product": submission.product,
            "productType": snapshot.product_type,
            "customerType": submission.payload["customerType"],
            "switch": snapshot.switch_payload_field,
            "switchEnabled": submission.payload[snapshot.switch_payload_field],
            "executionConfigVersion": snapshot.catalog_version,
            "applicationMethod": snapshot.method_code,
            "operation": snapshot.operation,
            "handler": snapshot.handler,
            "executionFields": list(snapshot.fields),
            "message": "示例产品参数校验完成",
            **handler_result,
        }

    @staticmethod
    def resolve_snapshot(job: Job, product_code: str) -> ProductExecutionSnapshot:
        if job.execution_config_snapshot:
            return ProductExecutionSnapshot.model_validate(job.execution_config_snapshot)
        return load_execution_catalog().snapshot(product_code)
