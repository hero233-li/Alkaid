from typing import ClassVar

from django.utils import timezone

from apps.integrations.application_link.adapter import ApplicationLinkAdapter
from apps.integrations.application_link.models import CreateApplicationRequest, GenerateLinksRequest
from apps.jobs.models import Job
from apps.product_data.application_links.schemas import (
    ApplicationLinkResult,
    ApplicationLinkSubmission,
    LinkCategory,
    submission_payload,
)


class BaseApplicationLinkHandler:
    """Defines the business sequence; the adapter owns outbound HTTP details."""

    code: ClassVar[str]
    category: ClassVar[LinkCategory]

    def generate(self, job: Job, submission: ApplicationLinkSubmission) -> ApplicationLinkResult:
        if submission.category != self.category:
            raise ValueError("申请链接处理器与类别不匹配")
        with ApplicationLinkAdapter(job) as adapter:
            application = adapter.create_application(
                CreateApplicationRequest(
                    product=submission.product,
                    category=submission.category.value,
                    payload=submission_payload(submission),
                )
            )
            links = adapter.generate_links(
                GenerateLinksRequest(
                    application_no=application.application_no,
                    product=submission.product,
                    category=submission.category.value,
                ),
                category=self.category,
            )
        return ApplicationLinkResult(
            internalUrl=links.internal_url,
            externalUrl=links.external_url,
            generatedAt=timezone.now().isoformat(),
            applicationNo=application.application_no,
        )
