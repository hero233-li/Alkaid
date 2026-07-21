from typing import Any

from apps.integrations.business_access.models import SearchBusinessAccessRequest
from apps.integrations.product_system.business_access import (
    invalidate_business_access,
    push_business_access_notification,
    query_business_access_notifications,
    search_business_access,
)
from apps.jobs.models import Job
from apps.product_data.business_access.schemas import (
    BusinessAccessCommand,
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
) -> dict[str, Any]:
    if "operation" in job.payload:
        command = BusinessAccessCommand.model_validate(job.payload)
        operation, data = command.operation, command.data
    else:
        operation = BusinessAccessOperation(job.kind.removeprefix("business_access."))
        data = job.payload
    if operation == BusinessAccessOperation.SEARCH:
        submission = BusinessAccessSearchSubmission.model_validate(data)
        if submission.environment not in BUSINESS_ACCESS_ENVIRONMENTS:
            raise ValueError("业务准入环境无效")
        records = search_business_access(
            job,
            SearchBusinessAccessRequest(
                environment=submission.environment,
                name=submission.name,
                certificate_no=submission.certificate_no,
            ),
        )
        return {"records": [_dump(record) for record in records]}

    if operation == BusinessAccessOperation.INVALIDATE:
        submission = BusinessAccessRecordSubmission.model_validate(data)
        return {"record": _dump(invalidate_business_access(job, submission.record_id))}

    if operation == BusinessAccessOperation.NOTIFICATIONS:
        submission = BusinessAccessRecordSubmission.model_validate(data)
        notifications = query_business_access_notifications(job, submission.record_id)
        return {"notifications": [_dump(item) for item in notifications]}

    if operation == BusinessAccessOperation.PUSH:
        submission = BusinessAccessPushSubmission.model_validate(data)
        result = push_business_access_notification(
            job,
            submission.record_id,
            submission.notification_id,
            submission.version_type,
        )
        return {"pushResult": _dump(result)}

    raise ValueError(f"不支持的业务准入操作：{operation}")


def _dump(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json", by_alias=True)
