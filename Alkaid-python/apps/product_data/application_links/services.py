import logging

from django.utils import timezone

from apps.integrations.application_link.adapter import ApplicationLinkAdapter
from apps.integrations.application_link.models import (
    CreateApplicationRequest,
    GenerateLinksRequest,
)
from apps.jobs.models import Job
from apps.product_data.application_links.schemas import (
    ApplicationLinkExecutionSnapshot,
    ApplicationLinkOption,
    ApplicationLinkPageConfig,
    ApplicationLinkProductConfig,
    ApplicationLinkResult,
    ApplicationLinkRouteConfig,
    ApplicationLinkSubmission,
    submission_payload,
)
from apps.product_data.catalog import ProductCatalog, ProductCatalogError, load_product_catalog

logger = logging.getLogger(__name__)


class ApplicationLinkConfigurationError(ValueError):
    pass


def normalize_submission(
    submission: ApplicationLinkSubmission,
) -> ApplicationLinkSubmission:
    """Translate legacy display labels into stable catalog codes at the HTTP boundary."""
    try:
        catalog = load_product_catalog()
        product = catalog.product(submission.product)
        environment = _environment_code(catalog, submission.environment)
    except ProductCatalogError as exc:
        raise ApplicationLinkConfigurationError("当前环境下没有该产品") from exc
    return submission.model_copy(
        update={"product": product.code, "environment": environment}
    )


def get_application_link_config() -> ApplicationLinkPageConfig:
    """Build page routing config from the backend product catalog."""
    catalog = load_product_catalog()
    products = tuple(
        ApplicationLinkProductConfig(
            label=product.name,
            value=product.code,
            routes=tuple(
                ApplicationLinkRouteConfig(
                    environment=_environment_code(catalog, route.environment),
                    category=route.category,
                    requiredFields=route.requiredFields,
                )
                for route in product.features.applicationLinks
            ),
        )
        for product in catalog.products.values()
        if product.features.applicationLinks
    )
    return ApplicationLinkPageConfig(
        environments=tuple(
            ApplicationLinkOption(label=option.label, value=option.value)
            for option in catalog.reference.environments
        ),
        products=products,
    )


def _environment_code(catalog: ProductCatalog, environment_code_or_label: str) -> str:
    for option in catalog.reference.environments:
        if environment_code_or_label in {option.value, option.label}:
            return option.value
    raise ProductCatalogError(f"未知环境：{environment_code_or_label}")


def resolve_execution_snapshot(
    submission: ApplicationLinkSubmission,
) -> ApplicationLinkExecutionSnapshot:
    """Resolve and freeze one link route directly from the product catalog."""
    try:
        catalog = load_product_catalog()
        configured_product = catalog.product(submission.product)
    except ProductCatalogError as exc:
        raise ApplicationLinkConfigurationError("当前环境下没有该产品") from exc

    environment_exists = any(
        _environment_code(catalog, route.environment) == submission.environment
        for route in configured_product.features.applicationLinks
    )
    if not environment_exists:
        raise ApplicationLinkConfigurationError("当前环境下没有该产品")

    for route in configured_product.features.applicationLinks:
        if (
            _environment_code(catalog, route.environment) == submission.environment
            and route.category == submission.category.value
        ):
            snapshot = ApplicationLinkExecutionSnapshot(
                config_version=catalog.reference.version,
                product=configured_product.code,
                environment=submission.environment,
                category=submission.category,
                required_fields=route.requiredFields,
            )
            validate_submission(submission, snapshot)
            return snapshot
    raise ApplicationLinkConfigurationError("当前产品在该环境下不支持该类别")


def validate_submission(
    submission: ApplicationLinkSubmission,
    snapshot: ApplicationLinkExecutionSnapshot,
) -> None:
    if (
        submission.product != snapshot.product
        or submission.environment != snapshot.environment
        or submission.category != snapshot.category
    ):
        raise ApplicationLinkConfigurationError("申请链接参数与 Job 执行配置不一致")
    missing = [
        name for name in snapshot.required_fields if not _has_submission_field(submission, name)
    ]
    if missing:
        raise ApplicationLinkConfigurationError(
            f"类别 {submission.category.value} 缺少必填字段：{', '.join(missing)}"
        )


def _has_submission_field(submission: ApplicationLinkSubmission, name: str) -> bool:
    """Accept fixed fields and fields supplied inside the dynamic JSON object."""

    value = getattr(submission, name, None)
    if value is None and submission.requestJson:
        value = submission.requestJson.get(name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def generate_application_links(
    job: Job,
    submission: ApplicationLinkSubmission,
    *,
    snapshot: ApplicationLinkExecutionSnapshot,
) -> ApplicationLinkResult:
    validate_submission(submission, snapshot)
    log_context = {
        "job_id": job.id,
        "workflow_id": str(job.workflow_id),
        "trace_id": job.trace_id,
        "product": submission.product,
        "environment": submission.environment,
        "category": submission.category.value,
    }
    logger.info("application_link_execution_started", extra=log_context)
    with ApplicationLinkAdapter(job) as adapter:
        application = adapter.create_application(
            CreateApplicationRequest(
                product=submission.product,
                category=submission.category.value,
                payload=submission_payload(submission),
            )
        )
        logger.info(
            "application_link_application_created",
            extra={**log_context, "application_no": application.application_no},
        )
        links = adapter.generate_links(
            GenerateLinksRequest(
                application_no=application.application_no,
                product=submission.product,
                category=submission.category.value,
            ),
            category=submission.category.value,
        )
    logger.info(
        "application_link_links_generated",
        extra={**log_context, "application_no": application.application_no},
    )
    return ApplicationLinkResult(
        internalUrl=links.internal_url,
        externalUrl=links.external_url,
        generatedAt=timezone.now().isoformat(),
        applicationNo=application.application_no,
    )
