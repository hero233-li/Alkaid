from typing import Any

from apps.integrations.verification_approval.adapter import VerificationApprovalAdapter
from apps.integrations.verification_approval.models import (
    SearchVerificationTaskRequest,
    VerificationTask,
)
from apps.jobs.models import Job
from apps.product_data.verification_approval.schemas import (
    VerificationAction,
    VerificationActionSubmission,
    VerificationItemJobSubmission,
    VerificationOperation,
    VerificationSearchSubmission,
    VerificationTaskOperationSubmission,
)

VERIFICATION_ENVIRONMENTS = ("环境1", "环境2", "环境3")
VERIFICATION_CATEGORIES = ("合同核实", "资料核实", "放款核实")


def get_verification_config() -> dict[str, object]:
    return {
        "environments": list(VERIFICATION_ENVIRONMENTS),
        "categories": list(VERIFICATION_CATEGORIES),
    }


def execute_verification_approval(
    job: Job,
    operation: VerificationOperation,
) -> dict[str, Any]:
    with VerificationApprovalAdapter(job) as adapter:
        if operation == VerificationOperation.SEARCH:
            submission = VerificationSearchSubmission.model_validate(job.payload)
            if submission.environment not in VERIFICATION_ENVIRONMENTS:
                raise ValueError("核实审批环境无效")
            if submission.category not in VERIFICATION_CATEGORIES:
                raise ValueError("核实审批类别无效")
            task = adapter.search(
                SearchVerificationTaskRequest(
                    environment=submission.environment,
                    category=submission.category,
                    contract_no=submission.contract_no,
                )
            )
            return {"task": _dump(task) if task is not None else None}

        if operation in {
            VerificationOperation.CLAIM,
            VerificationOperation.RETURN,
            VerificationOperation.REFRESH,
        }:
            submission = VerificationTaskOperationSubmission.model_validate(job.payload)
            context = submission.context
            _validate_context(context.id, context)
            if operation == VerificationOperation.CLAIM:
                task = adapter.claim(context.id, context)
            elif operation == VerificationOperation.RETURN:
                task = adapter.return_to_pool(context.id, context)
            else:
                task = adapter.refresh(context.id, context)
            return {"task": _dump(task)}

        if operation == VerificationOperation.ITEM_UPDATE:
            submission = VerificationItemJobSubmission.model_validate(job.payload)
            _validate_context(submission.context.id, submission.context)
            task = adapter.update_item(
                submission.context.id,
                submission.item_id,
                submission.status,
                submission.context,
            )
            return {"task": _dump(task)}

        if operation == VerificationOperation.ACTION:
            submission = VerificationActionSubmission.model_validate(job.payload)
            action = VerificationAction(submission.action)
            _validate_context(submission.context.id, submission.context)
            task = adapter.apply_action(
                submission.context.id,
                action.value,
                submission.context,
            )
            return {"task": _dump(task)}

    raise ValueError(f"不支持的核实审批操作：{operation}")


def _validate_context(task_id: str, context: VerificationTask) -> None:
    if context.id != task_id:
        raise ValueError("核实任务上下文与请求路径不一致")


def _dump(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json", by_alias=True)
