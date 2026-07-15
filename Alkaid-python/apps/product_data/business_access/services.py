from typing import Any

from apps.integrations.business_access.adapter import BusinessAccessAdapter
from apps.integrations.business_access.models import SearchBusinessAccessRequest
from apps.jobs.models import Job
from apps.product_data.business_access.schemas import (
    BusinessAccessOperation,
    BusinessAccessPushSubmission,
    BusinessAccessRecordSubmission,
    BusinessAccessSearchSubmission,
)

BUSINESS_ACCESS_ENVIRONMENTS = ("环境1", "环境2", "环境3")


def get_business_access_config() -> dict[str, object]:
    return {"environments": list(BUSINESS_ACCESS_ENVIRONMENTS)}


def execute_business_access(
    job: Job,
    operation: BusinessAccessOperation,
) -> dict[str, Any]:
    with BusinessAccessAdapter(job) as adapter:
        if operation == BusinessAccessOperation.SEARCH:
            submission = BusinessAccessSearchSubmission.model_validate(job.payload)
            if submission.environment not in BUSINESS_ACCESS_ENVIRONMENTS:
                raise ValueError("业务准入环境无效")
            records = adapter.search(
                SearchBusinessAccessRequest(
                    environment=submission.environment,
                    name=submission.name,
                    certificate_no=submission.certificate_no,
                )
            )
            return {"records": [_dump(record) for record in records]}

        if operation == BusinessAccessOperation.INVALIDATE:
            submission = BusinessAccessRecordSubmission.model_validate(job.payload)
            return {"record": _dump(adapter.invalidate(submission.record_id))}

        if operation == BusinessAccessOperation.NOTIFICATIONS:
            submission = BusinessAccessRecordSubmission.model_validate(job.payload)
            notifications = adapter.query_notifications(submission.record_id)
            return {"notifications": [_dump(item) for item in notifications]}

        if operation == BusinessAccessOperation.PUSH:
            submission = BusinessAccessPushSubmission.model_validate(job.payload)
            result = adapter.push_notification(
                submission.record_id,
                submission.notification_id,
                submission.version_type,
            )
            return {"pushResult": _dump(result)}

    raise ValueError(f"不支持的业务准入操作：{operation}")


def _dump(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json", by_alias=True)
