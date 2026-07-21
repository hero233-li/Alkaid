from typing import Any

from apps.integrations.application_link.models import GenerateApplicationLinkRequest
from apps.integrations.mock_product.models import ProductCheckInput, ProductSubmissionInput
from apps.integrations.product_system.application_link import generate_application_link
from apps.integrations.product_system.product_application import ProductApplicationSession
from apps.jobs.models import Job
from apps.jobs.steps import save_job_step
from apps.product_data.catalog import (
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


# Public entry point
def execute_product_application(job: Job) -> dict[str, Any]:
    submission = ProductApplicationSubmission(
        name=job.name,
        product=job.product,
        payload=job.payload,
    )
    snapshot = resolve_product_snapshot(job, job.product)
    validate_submission(submission, execution_snapshot=snapshot)
    return run_product_application(job, submission, snapshot=snapshot)


# Validation
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
    if product is not None and payload.get("environment") not in product.environments:
        raise ProductConfigurationError("当前环境不支持该产品")

    customer_type = validate_customer_type(payload)
    if payload.get("applicationMethod") != execution_snapshot.method_code:
        raise ProductConfigurationError("申请方式与 Job 执行配置不一致")
    known_fields = set(execution_snapshot.fields)
    unknown_fields = set(payload) - known_fields
    if unknown_fields:
        raise ProductConfigurationError(f"提交了未知字段：{', '.join(sorted(unknown_fields))}")
    required_fields = set(execution_snapshot.required_fields)
    missing = [
        name for name in required_fields if payload.get(name) is None or payload.get(name) == ""
    ]
    if missing:
        raise ProductConfigurationError(f"缺少必填字段：{', '.join(sorted(missing))}")

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


# Main workflow
def run_product_application(
    job: Job,
    submission: ProductApplicationSubmission,
    *,
    snapshot: ProductExecutionSnapshot | None = None,
) -> dict[str, Any]:
    snapshot = snapshot or resolve_product_snapshot(job, submission.product)
    if snapshot.product_code != submission.product:
        raise ProductConfigurationError("Job 执行配置与提交产品不一致")
    result = dict(job.result or {})
    if "links" not in result:
        links = generate_application_link(job, build_link_request(submission))
        save_job_step(
            job,
            "links",
            links.model_dump(mode="json"),
            stage="links_completed",
            progress=35,
            message="申请链接生成完成",
        )
        result = dict(job.result)

    if "application" not in result or "followup" not in result:
        with ProductApplicationSession(job) as session:
            if "application" not in result:
                application = submit_product_application(session, submission, snapshot)
                save_job_step(
                    job,
                    "application",
                    application,
                    stage="application_completed",
                    progress=80,
                    message="产品申请提交完成",
                )
                result = dict(job.result)
            if "followup" not in result:
                session.audit(session.request_head())
                save_job_step(
                    job,
                    "followup",
                    {"status": "success"},
                    stage="followup_completed",
                    progress=95,
                    message="产品申请后续审计完成",
                )
                result = dict(job.result)

    application = result["application"]
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
        "message": "示例产品参数校验完成",
        "applicationNo": application["applicationNo"],
        "flowTokenVersions": application["flowTokenVersions"],
        "fixedTokenCall": "success",
        **result,
    }


# Request builder
def build_link_request(
    submission: ProductApplicationSubmission,
) -> GenerateApplicationLinkRequest:
    product = load_product_catalog().product(submission.product)
    environment = str(submission.payload["environment"])
    route = next(
        (item for item in product.features.applicationLinks if item.environment == environment),
        None,
    )
    if route is None:
        raise ProductConfigurationError("当前产品和环境未配置申请链接")
    certificate_no = str(submission.payload["certificateNo"])
    return GenerateApplicationLinkRequest(
        env=environment,
        product=submission.product,
        category=route.category,
        cooperation_project_id=None,
        payload={
            "loanType": submission.payload["applicationMethod"],
            "customerName": submission.payload["personName"],
            "customerPhone": submission.payload["phone"],
            "customerCertificateNo": certificate_no,
            "customerCompanyName": submission.payload.get("companyName") or "",
            "customerCompanyCode": submission.payload.get("creditCode") or "",
            "openId": f"OPEN-{certificate_no[-8:]}",
            "unionId": f"UNION-{certificate_no[-8:]}",
        },
    )


def submit_product_application(
    session: ProductApplicationSession,
    submission: ProductApplicationSubmission,
    snapshot: ProductExecutionSnapshot,
) -> dict[str, object]:
    request_head = session.request_head()
    session.login(request_head)
    version_after_login = session.flow_token_version
    session.check_product(
        request_head,
        ProductCheckInput(
            product=snapshot.product_code,
            customer_type=submission.payload["customerType"],
            switch_name=snapshot.switch_field,
            switch_enabled=bool(submission.payload[snapshot.switch_field]),
            product_type=snapshot.product_type,
        ),
    )
    version_after_check = session.flow_token_version
    session.rotate_token(request_head)
    version_after_rotate = session.flow_token_version
    application = session.submit_application(
        request_head,
        ProductSubmissionInput(
            product=submission.product,
            environment=submission.payload["environment"],
            product_type=snapshot.product_type,
            organization_code=submission.payload["branch"],
            customer_name=submission.payload["personName"],
            certificate_no=submission.payload["certificateNo"],
            phone=submission.payload["phone"],
            customer_type=submission.payload["customerType"],
            outlet_code=submission.payload["outlet"],
            application_method=submission.payload["applicationMethod"],
            risk={
                name: submission.payload[name]
                for name in (
                    "whitelistEnabled",
                    "redShieldEnabled",
                    "creditEnabled",
                )
                if name in submission.payload
            },
            dynamic_term=submission.payload.get("dynamicTerm"),
            dynamic_amount=submission.payload.get("dynamicAmount"),
            extra_reason=submission.payload.get("extraReason"),
        ),
    )
    version_after_submit = session.flow_token_version

    return {
        "applicationNo": application.data["applicationNo"],
        "flowTokenVersions": {
            "login": version_after_login,
            "check": version_after_check,
            "rotate": version_after_rotate,
            "submit": version_after_submit,
        },
    }
