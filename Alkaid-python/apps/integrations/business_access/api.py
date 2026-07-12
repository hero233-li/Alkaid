from dataclasses import replace

from apps.integrations.business_access.models import (
    BusinessAccessNotificationsResponse,
    BusinessAccessRecordResponse,
    NotificationPushResponse,
    SearchBusinessAccessResponse,
)
from apps.integrations.contracts import EndpointSpec, RetryMode

SEARCH_BUSINESS_ACCESS = EndpointSpec(
    operation_id="business_access.search",
    method="POST",
    path="/access/records/search",
    response_model=SearchBusinessAccessResponse,
    success_path="code",
    success_values=("0000",),
    retry_mode=RetryMode.SAFE,
)

INVALIDATE_BUSINESS_ACCESS = EndpointSpec(
    operation_id="business_access.invalidate",
    method="POST",
    path="/access/records/{record_id}/invalidate",
    response_model=BusinessAccessRecordResponse,
    success_path="code",
    success_values=("0000",),
)

QUERY_BUSINESS_ACCESS_NOTIFICATIONS = EndpointSpec(
    operation_id="business_access.notifications.query",
    method="POST",
    path="/access/records/{record_id}/notifications/query",
    response_model=BusinessAccessNotificationsResponse,
    success_path="code",
    success_values=("0000",),
    retry_mode=RetryMode.SAFE,
)

PUSH_BUSINESS_ACCESS_NOTIFICATION = EndpointSpec(
    operation_id="business_access.notifications.push",
    method="POST",
    path="/access/records/{record_id}/notifications/{notification_id}/push",
    response_model=NotificationPushResponse,
    success_path="code",
    success_values=("0000",),
)


def invalidate_endpoint(record_id: int):
    return replace(
        INVALIDATE_BUSINESS_ACCESS,
        path=INVALIDATE_BUSINESS_ACCESS.path.format(record_id=record_id),
    )


def query_notifications_endpoint(record_id: int):
    return replace(
        QUERY_BUSINESS_ACCESS_NOTIFICATIONS,
        path=QUERY_BUSINESS_ACCESS_NOTIFICATIONS.path.format(record_id=record_id),
    )


def push_notification_endpoint(record_id: int, notification_id: int):
    return replace(
        PUSH_BUSINESS_ACCESS_NOTIFICATION,
        path=PUSH_BUSINESS_ACCESS_NOTIFICATION.path.format(
            record_id=record_id,
            notification_id=notification_id,
        ),
    )
