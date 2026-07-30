from collections.abc import Callable

from apps.jobs.models import Job
from apps.product_data.application_links.context import ApplicationLinkContext
from apps.product_data.application_links.schemas import (
    ApplicationLinkExecutionSnapshot,
    ApplicationLinkResult,
    ApplicationLinkSubmission,
)
from apps.product_data.application_links.services import (
    generate_application_links,
    normalize_submission,
    resolve_execution_snapshot,
    validate_submission,
)

ProgressReporter = Callable[..., None]


class ApplicationLinkFlow:
    """Execute the application-link business flow in explicit Python order."""

    def execute(
        self,
        *,
        job: Job,
        progress: ProgressReporter | None = None,
    ) -> ApplicationLinkResult:
        context = self.create_context(job)

        self.parse_submission(context)
        self.load_execution_snapshot(context)
        self.normalize_legacy_submission(context)
        self.resolve_legacy_execution_snapshot(context)
        self.validate_submission(context)
        self.report_validation_completed(progress)
        self.generate_links(context)
        self.report_generation_completed(progress)

        return self.result(context)

    @staticmethod
    def create_context(job: Job) -> ApplicationLinkContext:
        return ApplicationLinkContext(job=job, payload=dict(job.payload))

    @staticmethod
    def parse_submission(context: ApplicationLinkContext) -> None:
        context.submission = ApplicationLinkSubmission.model_validate(context.payload)

    @staticmethod
    def load_execution_snapshot(context: ApplicationLinkContext) -> None:
        if context.job.execution_config_snapshot:
            context.execution_snapshot = ApplicationLinkExecutionSnapshot.model_validate(
                context.job.execution_config_snapshot
            )

    @staticmethod
    def normalize_legacy_submission(context: ApplicationLinkContext) -> None:
        if context.execution_snapshot is None:
            context.submission = normalize_submission(ApplicationLinkFlow._submission(context))

    @staticmethod
    def resolve_legacy_execution_snapshot(context: ApplicationLinkContext) -> None:
        if context.execution_snapshot is None:
            context.execution_snapshot = resolve_execution_snapshot(
                ApplicationLinkFlow._submission(context)
            )

    @staticmethod
    def validate_submission(context: ApplicationLinkContext) -> None:
        validate_submission(
            ApplicationLinkFlow._submission(context),
            ApplicationLinkFlow._execution_snapshot(context),
        )

    @staticmethod
    def report_validation_completed(progress: ProgressReporter | None) -> None:
        if progress is not None:
            progress(stage="validate", progress=30, message="申请链接参数校验完成")

    @staticmethod
    def generate_links(context: ApplicationLinkContext) -> None:
        context.result = generate_application_links(
            context.job,
            ApplicationLinkFlow._submission(context),
            snapshot=ApplicationLinkFlow._execution_snapshot(context),
        )

    @staticmethod
    def report_generation_completed(progress: ProgressReporter | None) -> None:
        if progress is not None:
            progress(
                stage="generate",
                progress=90,
                message="申请链接生成完成，正在保存结果",
            )

    @staticmethod
    def result(context: ApplicationLinkContext) -> ApplicationLinkResult:
        if context.result is None:
            raise RuntimeError("申请链接流程没有生成结果")
        return context.result

    @staticmethod
    def _submission(context: ApplicationLinkContext) -> ApplicationLinkSubmission:
        if context.submission is None:
            raise RuntimeError("申请链接流程尚未解析提交参数")
        return context.submission

    @staticmethod
    def _execution_snapshot(
        context: ApplicationLinkContext,
    ) -> ApplicationLinkExecutionSnapshot:
        if context.execution_snapshot is None:
            raise RuntimeError("申请链接流程尚未解析执行配置")
        return context.execution_snapshot
