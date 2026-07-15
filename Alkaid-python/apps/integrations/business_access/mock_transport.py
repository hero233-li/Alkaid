import hashlib
import json
import re
from datetime import datetime, timezone
from threading import Lock

import httpx
from pydantic import ValidationError

from apps.integrations.business_access.models import (
    BusinessAccessNotification,
    BusinessAccessRecord,
    PushNotificationRequest,
    RecordOperationRequest,
    SearchBusinessAccessRequest,
)

RECORD_ACTION_PATH = re.compile(
    r"^/access/records/(?P<record_id>\d+)/(?P<action>invalidate|notifications/query)$"
)
PUSH_PATH = re.compile(
    r"^/access/records/(?P<record_id>\d+)/notifications/(?P<notification_id>\d+)/push$"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MockBusinessAccessStore:
    """External-system state used only by the mock transport; reset when the worker restarts."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[int, BusinessAccessRecord] = {}
        self._notifications: dict[int, tuple[BusinessAccessNotification, ...]] = {}

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._notifications.clear()

    def search(self, request: SearchBusinessAccessRequest) -> tuple[BusinessAccessRecord, ...]:
        seed_text = "|".join(
            (request.environment, request.name or "", request.certificate_no or "")
        )
        seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:8], 16) % 800000 + 100000
        record_count = 1 if request.certificate_no else 2
        records: list[BusinessAccessRecord] = []
        with self._lock:
            for offset in range(record_count):
                record_id = seed * 10 + offset + 1
                candidate = BusinessAccessRecord(
                    id=record_id,
                    business_no=f"BA{record_id}",
                    customer_name=request.name or ("马凡" if offset == 0 else "马帆"),
                    certificate_no=request.certificate_no
                    or ("21060419951125196X" if offset == 0 else "220102198812120018"),
                    product_name="吉农e贷" if offset == 0 else "普惠经营贷",
                    organization_name="吉林省分行营业部" if offset == 0 else "长春朝阳支行",
                    access_result="通过" if offset == 0 else "人工复核",
                    status="valid",
                    queried_at=_now(),
                )
                record = self._records.setdefault(record_id, candidate)
                records.append(record)
        return tuple(records)

    def invalidate(self, record_id: int) -> BusinessAccessRecord:
        with self._lock:
            record = self._records[record_id]
            updated = record.model_copy(update={"status": "invalid"})
            self._records[record_id] = updated
            return updated

    def notifications(self, record_id: int) -> tuple[BusinessAccessNotification, ...]:
        with self._lock:
            if record_id not in self._records:
                raise KeyError(record_id)
            if record_id not in self._notifications:
                self._notifications[record_id] = (
                    BusinessAccessNotification(
                        id=record_id * 10 + 1,
                        notification_no=f"NT{record_id}01",
                        notification_type="准入结果通知",
                        target_system="合作方渠道系统",
                        latest_version="V3",
                        previous_version="V2",
                        updated_at=_now(),
                    ),
                    BusinessAccessNotification(
                        id=record_id * 10 + 2,
                        notification_no=f"NT{record_id}02",
                        notification_type="客户状态通知",
                        target_system="客户运营平台",
                        latest_version="V2",
                        previous_version="V1",
                        updated_at=_now(),
                    ),
                )
            return self._notifications[record_id]

    def push(self, request: PushNotificationRequest) -> dict[str, object]:
        notifications = self.notifications(request.record_id)
        notification = next(
            (item for item in notifications if item.id == request.notification_id),
            None,
        )
        if notification is None:
            raise KeyError(request.notification_id)
        version = (
            notification.latest_version
            if request.version_type == "latest"
            else notification.previous_version
        )
        return {
            "businessRecordId": request.record_id,
            "notificationId": request.notification_id,
            "versionType": request.version_type,
            "version": version,
            "pushedAt": _now(),
            "message": f"通知 {notification.notification_no} 的 {version} 版本已推送",
        }


BUSINESS_ACCESS_MOCK_STORE = MockBusinessAccessStore()


def create_business_access_mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        try:
            payload = json.loads(request.content.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        try:
            if request.url.path == "/access/records/search":
                search = SearchBusinessAccessRequest.model_validate(payload)
                records = BUSINESS_ACCESS_MOCK_STORE.search(search)
                return _ok({"records": _dump_many(records)}, "业务准入查询成功")

            action_match = RECORD_ACTION_PATH.match(request.url.path)
            if action_match:
                record_id = int(action_match.group("record_id"))
                RecordOperationRequest(record_id=record_id)
                if action_match.group("action") == "invalidate":
                    record = BUSINESS_ACCESS_MOCK_STORE.invalidate(record_id)
                    return _ok({"record": _dump(record)}, "业务准入记录已失效")
                notifications = BUSINESS_ACCESS_MOCK_STORE.notifications(record_id)
                return _ok(
                    {"notifications": _dump_many(notifications)},
                    "通知记录查询成功",
                )

            push_match = PUSH_PATH.match(request.url.path)
            if push_match:
                push = PushNotificationRequest(
                    record_id=int(push_match.group("record_id")),
                    notification_id=int(push_match.group("notification_id")),
                    version_type=payload.get("version_type") or payload.get("versionType"),
                )
                return _ok(
                    {"pushResult": BUSINESS_ACCESS_MOCK_STORE.push(push)},
                    "通知推送成功",
                )
        except ValidationError as exc:
            return httpx.Response(400, json={"code": "INVALID_REQUEST", "message": str(exc)})
        except KeyError:
            return httpx.Response(404, json={"code": "NOT_FOUND", "message": "记录不存在"})
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "接口不存在"})

    return httpx.MockTransport(handler)


def _dump(value: BusinessAccessRecord | BusinessAccessNotification) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True)


def _dump_many(
    values: tuple[BusinessAccessRecord, ...] | tuple[BusinessAccessNotification, ...],
) -> list[dict[str, object]]:
    return [_dump(value) for value in values]


def _ok(data: dict[str, object], message: str) -> httpx.Response:
    return httpx.Response(200, json={"code": "0000", "message": message, "data": data})
