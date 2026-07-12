from typing import Any

from apps.integrations.verification_approval.adapter import VerificationApprovalAdapter
from apps.integrations.verification_approval.models import SearchVerificationTaskRequest
from apps.product_data.verification_approval.schemas import (
    VerificationAction,
    VerificationSearchSubmission,
)

VERIFICATION_ENVIRONMENTS = ("环境1", "环境2", "环境3")
VERIFICATION_CATEGORIES = ("合同核实", "资料核实", "放款核实")


def get_verification_config() -> dict[str, object]:
    return {
        "environments": list(VERIFICATION_ENVIRONMENTS),
        "categories": list(VERIFICATION_CATEGORIES),
    }


def search_verification_task(
    submission: VerificationSearchSubmission,
    *,
    trace_id: str,
) -> dict[str, Any] | None:
    if submission.environment not in VERIFICATION_ENVIRONMENTS:
        raise ValueError("核实审批环境无效")
    if submission.category not in VERIFICATION_CATEGORIES:
        raise ValueError("核实审批类别无效")
    with VerificationApprovalAdapter(trace_id) as adapter:
        task = adapter.search(
            SearchVerificationTaskRequest(
                environment=submission.environment,
                category=submission.category,
                contract_no=submission.contract_no,
            )
        )
    return _dump(task) if task is not None else None


def claim_verification_task(task_id: str, *, trace_id: str) -> dict[str, Any]:
    with VerificationApprovalAdapter(trace_id) as adapter:
        return _dump(adapter.claim(task_id))


def return_verification_task(task_id: str, *, trace_id: str) -> dict[str, Any]:
    with VerificationApprovalAdapter(trace_id) as adapter:
        return _dump(adapter.return_to_pool(task_id))


def update_verification_item(
    task_id: str,
    item_id: str,
    status: str,
    *,
    trace_id: str,
) -> dict[str, Any]:
    with VerificationApprovalAdapter(trace_id) as adapter:
        return _dump(adapter.update_item(task_id, item_id, status))


def apply_verification_action(
    task_id: str,
    action: VerificationAction,
    *,
    trace_id: str,
) -> dict[str, Any]:
    with VerificationApprovalAdapter(trace_id) as adapter:
        return _dump(adapter.apply_action(task_id, action.value))


def _dump(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json", by_alias=True)
