from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class WireModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class SearchBusinessAccessRequest(WireModel):
    environment: str = Field(min_length=1, max_length=128)
    name: str | None = Field(default=None, max_length=128)
    certificate_no: str | None = Field(default=None, max_length=64)


class RecordOperationRequest(WireModel):
    record_id: int = Field(gt=0)


class PushNotificationRequest(WireModel):
    record_id: int = Field(gt=0)
    notification_id: int = Field(gt=0)
    version_type: Literal["latest", "previous"]


class BusinessAccessRecord(WireModel):
    id: int
    business_no: str
    customer_name: str
    certificate_no: str
    product_name: str
    organization_name: str
    access_result: Literal["通过", "人工复核", "拒绝"]
    status: Literal["valid", "invalid"]
    queried_at: str


class BusinessAccessNotification(WireModel):
    id: int
    notification_no: str
    notification_type: str
    target_system: str
    latest_version: str
    previous_version: str
    updated_at: str


class NotificationPushResult(WireModel):
    business_record_id: int
    notification_id: int
    version_type: Literal["latest", "previous"]
    version: str
    pushed_at: str
    message: str


class SearchBusinessAccessData(WireModel):
    records: tuple[BusinessAccessRecord, ...]


class BusinessAccessRecordData(WireModel):
    record: BusinessAccessRecord


class BusinessAccessNotificationsData(WireModel):
    notifications: tuple[BusinessAccessNotification, ...]


class NotificationPushData(WireModel):
    push_result: NotificationPushResult


class SearchBusinessAccessResponse(WireModel):
    code: str
    message: str
    data: SearchBusinessAccessData


class BusinessAccessRecordResponse(WireModel):
    code: str
    message: str
    data: BusinessAccessRecordData


class BusinessAccessNotificationsResponse(WireModel):
    code: str
    message: str
    data: BusinessAccessNotificationsData


class NotificationPushResponse(WireModel):
    code: str
    message: str
    data: NotificationPushData
