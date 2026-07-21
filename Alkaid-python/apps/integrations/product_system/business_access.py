from pydantic import BaseModel

from apps.integrations.auth import TokenManager
from apps.integrations.business_access.api import (
    SEARCH_BUSINESS_ACCESS,
    invalidate_endpoint,
    push_notification_endpoint,
    query_notifications_endpoint,
)
from apps.integrations.business_access.models import (
    BusinessAccessNotification,
    BusinessAccessRecord,
    NotificationPushResult,
    PushNotificationRequest,
    RecordOperationRequest,
    SearchBusinessAccessRequest,
)
from apps.integrations.executor import EndpointExecutor
from apps.integrations.product_system.client import create_product_system_client
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


def search_business_access(
    job: Job, request: SearchBusinessAccessRequest
) -> tuple[BusinessAccessRecord, ...]:
    return _execute(job, "business_access.search", SEARCH_BUSINESS_ACCESS, request).data.records


def invalidate_business_access(job: Job, record_id: int) -> BusinessAccessRecord:
    return _execute(
        job,
        "business_access.invalidate",
        invalidate_endpoint(record_id),
        RecordOperationRequest(record_id=record_id),
    ).data.record


def query_business_access_notifications(
    job: Job, record_id: int
) -> tuple[BusinessAccessNotification, ...]:
    return _execute(
        job,
        "business_access.notifications.query",
        query_notifications_endpoint(record_id),
        RecordOperationRequest(record_id=record_id),
    ).data.notifications


def push_business_access_notification(
    job: Job, record_id: int, notification_id: int, version_type: str
) -> NotificationPushResult:
    return _execute(
        job,
        "business_access.notifications.push",
        push_notification_endpoint(record_id, notification_id),
        PushNotificationRequest(
            record_id=record_id,
            notification_id=notification_id,
            version_type=version_type,
        ),
    ).data.push_result


def _execute(job: Job, step: str, endpoint, body: BaseModel):
    client = create_product_system_client("business_access")
    try:
        return EndpointExecutor(client, TokenManager({})).execute(
            endpoint,
            body=body,
            trace_id=job.trace_id,
            observer=JobHttpCallObserver(job, step=step),
        )
    finally:
        client.close()
