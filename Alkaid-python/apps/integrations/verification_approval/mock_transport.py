import copy
import hashlib
import json
import re
from threading import Lock

import httpx
from pydantic import ValidationError

from apps.integrations.verification_approval.models import (
    SearchVerificationTaskRequest,
    VerificationActionRequest,
    VerificationItem,
    VerificationItemUpdateRequest,
    VerificationTask,
)

TASK_ACTION_PATH = re.compile(r"^/verification/tasks/(?P<task_id>[^/]+)/(?P<action>claim|return)$")
ITEM_PATH = re.compile(r"^/verification/tasks/(?P<task_id>[^/]+)/items/(?P<item_id>[^/]+)$")
QUICK_ACTION_PATH = re.compile(
    r"^/verification/tasks/(?P<task_id>[^/]+)/actions/(?P<action>[^/]+)$"
)
ITEM_TEMPLATES = (
    ("identity", "客户身份核实"),
    ("contract", "合同信息核实"),
    ("account", "收款账户核实"),
    ("enterprise", "企业资料核实"),
    ("loan", "贷款要素核实"),
    ("approval", "审批资料核实"),
)


class MockVerificationConflict(ValueError):
    pass


class MockVerificationStore:
    """External mock task pool. Real mode replaces this store with the actual system."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._tasks: dict[str, VerificationTask] = {}

    def reset(self) -> None:
        with self._lock:
            self._tasks.clear()

    def search(self, request: SearchVerificationTaskRequest) -> VerificationTask | None:
        if request.contract_no == "0":
            return None
        digest = (
            hashlib.sha256(
                f"{request.environment}|{request.category}|{request.contract_no}".encode()
            )
            .hexdigest()[:12]
            .upper()
        )
        task_id = f"VERIFY-{digest}"
        with self._lock:
            if task_id not in self._tasks:
                claimed = request.contract_no == "2"
                self._tasks[task_id] = VerificationTask(
                    id=task_id,
                    contract_no=request.contract_no,
                    ownership_status="claimed" if claimed else "unclaimed",
                    task_status="核实中" if claimed else "待领取",
                    node="核实审批",
                    teller_no="T1027",
                    organization_no="510001",
                    product_name=("经营快贷" if request.category == "合同核实" else "普惠经营贷"),
                    items=tuple(
                        VerificationItem(id=item_id, title=title, status="pending")
                        for item_id, title in ITEM_TEMPLATES
                    ),
                )
            return copy.deepcopy(self._tasks[task_id])

    def claim(self, task_id: str) -> VerificationTask:
        return self._update(
            task_id,
            lambda task: task.model_copy(
                update={"ownership_status": "claimed", "task_status": "核实中"}
            ),
        )

    def return_to_pool(self, task_id: str) -> VerificationTask:
        return self._update(
            task_id,
            lambda task: task.model_copy(
                update={
                    "ownership_status": "unclaimed",
                    "task_status": "待领取",
                    "items": tuple(
                        item.model_copy(update={"status": "pending"}) for item in task.items
                    ),
                }
            ),
        )

    def update_item(
        self,
        task_id: str,
        item_id: str,
        request: VerificationItemUpdateRequest,
    ) -> VerificationTask:
        def mutate(task: VerificationTask) -> VerificationTask:
            self._require_claimed(task)
            if not any(item.id == item_id for item in task.items):
                raise KeyError(item_id)
            return task.model_copy(
                update={
                    "items": tuple(
                        item.model_copy(update={"status": request.status})
                        if item.id == item_id
                        else item
                        for item in task.items
                    )
                }
            )

        return self._update(task_id, mutate)

    def apply_action(
        self,
        task_id: str,
        request: VerificationActionRequest,
    ) -> VerificationTask:
        def mutate(task: VerificationTask) -> VerificationTask:
            self._require_claimed(task)
            if request.action == "complete":
                return task.model_copy(
                    update={
                        "task_status": "核实完成",
                        "items": tuple(
                            item.model_copy(update={"status": "completed"}) for item in task.items
                        ),
                    }
                )
            if request.action == "supplement":
                return task.model_copy(update={"task_status": "待补件"})
            if request.action == "submit":
                if not all(item.status == "completed" for item in task.items):
                    raise MockVerificationConflict("全部核实项完成后才能提交")
                return task.model_copy(update={"task_status": "已提交"})
            return task.model_copy(update={"task_status": "审批已提交"})

        return self._update(task_id, mutate)

    def _update(self, task_id: str, mutate) -> VerificationTask:
        with self._lock:
            task = self._tasks[task_id]
            updated = mutate(task)
            self._tasks[task_id] = updated
            return copy.deepcopy(updated)

    @staticmethod
    def _require_claimed(task: VerificationTask) -> None:
        if task.ownership_status != "claimed":
            raise MockVerificationConflict("请先领取核实任务")


VERIFICATION_APPROVAL_MOCK_STORE = MockVerificationStore()


def create_verification_approval_mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        try:
            payload = json.loads(request.content.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        try:
            if request.url.path == "/verification/tasks/search":
                search = SearchVerificationTaskRequest.model_validate(payload)
                return _ok(VERIFICATION_APPROVAL_MOCK_STORE.search(search), "核实任务查询成功")

            task_action = TASK_ACTION_PATH.match(request.url.path)
            if task_action:
                task_id = task_action.group("task_id")
                task = (
                    VERIFICATION_APPROVAL_MOCK_STORE.claim(task_id)
                    if task_action.group("action") == "claim"
                    else VERIFICATION_APPROVAL_MOCK_STORE.return_to_pool(task_id)
                )
                return _ok(task, "核实任务状态更新成功")

            item_match = ITEM_PATH.match(request.url.path)
            if item_match:
                update = VerificationItemUpdateRequest.model_validate(payload)
                task = VERIFICATION_APPROVAL_MOCK_STORE.update_item(
                    item_match.group("task_id"),
                    item_match.group("item_id"),
                    update,
                )
                return _ok(task, "核实项状态更新成功")

            action_match = QUICK_ACTION_PATH.match(request.url.path)
            if action_match:
                action = VerificationActionRequest.model_validate(
                    {**payload, "action": action_match.group("action")}
                )
                task = VERIFICATION_APPROVAL_MOCK_STORE.apply_action(
                    action_match.group("task_id"),
                    action,
                )
                return _ok(task, "核实审批操作成功")
        except ValidationError as exc:
            return httpx.Response(400, json={"code": "INVALID_REQUEST", "message": str(exc)})
        except KeyError:
            return httpx.Response(404, json={"code": "NOT_FOUND", "message": "核实任务不存在"})
        except MockVerificationConflict as exc:
            return httpx.Response(409, json={"code": "CONFLICT", "message": str(exc)})
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "接口不存在"})

    return httpx.MockTransport(handler)


def _ok(task: VerificationTask | None, message: str) -> httpx.Response:
    data = task.model_dump(mode="json", by_alias=True) if task is not None else None
    return httpx.Response(200, json={"code": "0000", "message": message, "data": data})
