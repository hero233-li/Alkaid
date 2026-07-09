from apps.jobs.models import Job
from apps.product_data.application_links.config import (
    APPLICATION_LINK_CONFIG_VERSION,
    ApplicationLinkConfigurationError,
    get_application_link_route,
)
from apps.product_data.application_links.handlers import get_application_link_handler
from apps.product_data.application_links.schemas import (
    ApplicationLinkExecutionSnapshot,
    ApplicationLinkResult,
    ApplicationLinkSubmission,
)


def resolve_execution_snapshot(
    submission: ApplicationLinkSubmission,
) -> ApplicationLinkExecutionSnapshot:
    route = get_application_link_route(
        submission.product,
        submission.environment,
        submission.category,
    )
    snapshot = ApplicationLinkExecutionSnapshot(
        config_version=APPLICATION_LINK_CONFIG_VERSION,
        product=submission.product,
        environment=submission.environment,
        category=submission.category,
        handler=route.handler,
        required_fields=route.required_fields,
    )
    validate_submission(submission, snapshot)
    return snapshot


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
        name
        for name in snapshot.required_fields
        if not (getattr(submission, name, None) or "").strip()
    ]
    if missing:
        raise ApplicationLinkConfigurationError(
            f"类别 {submission.category.value} 缺少必填字段：{', '.join(missing)}"
        )


class ApplicationLinkGenerator:
    def generate(
        self,
        job: Job,
        submission: ApplicationLinkSubmission,
        *,
        snapshot: ApplicationLinkExecutionSnapshot,
    ) -> ApplicationLinkResult:
        validate_submission(submission, snapshot)
        return get_application_link_handler(snapshot.handler).generate(job, submission)
