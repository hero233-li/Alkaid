from typing import Any

from apps.integrations.product_system.verification_approval import (
    apply_verification_action,
    claim_verification_task,
    refresh_verification_task,
    return_verification_task,
    search_verification_task,
    update_verification_item,
)
from apps.integrations.verification_approval.models import (
    SearchVerificationTaskRequest,
)
from apps.jobs.models import Job
from apps.product_data.verification_approval.schemas import (
    VerificationAction,
    VerificationActionSubmission,
    VerificationCommand,
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
) -> dict[str, Any]:
    if "operation" in job.payload:
        command = VerificationCommand.model_validate(job.payload)
        operation, data = command.operation, command.data
    else:
        operation = VerificationOperation(job.kind.removeprefix("verification_approval."))
        data = job.payload
    if operation == VerificationOperation.SEARCH:
        submission = VerificationSearchSubmission.model_validate(data)
        if submission.environment not in VERIFICATION_ENVIRONMENTS:
            raise ValueError("核实审批环境无效")
        if submission.category not in VERIFICATION_CATEGORIES:
            raise ValueError("核实审批类别无效")
        task = search_verification_task(
            job,
            SearchVerificationTaskRequest(
                environment=submission.environment,
                category=submission.category,
                contract_no=submission.contract_no,
            ),
        )
        return {"task": _dump(task) if task is not None else None}

    if operation in {
        VerificationOperation.CLAIM,
        VerificationOperation.RETURN,
        VerificationOperation.REFRESH,
    }:
        submission = VerificationTaskOperationSubmission.model_validate(data)
        context = submission.context
        if operation == VerificationOperation.CLAIM:
            task = claim_verification_task(job, context.id, context)
        elif operation == VerificationOperation.RETURN:
            task = return_verification_task(job, context.id, context)
        else:
            task = refresh_verification_task(job, context.id, context)
        return {"task": _dump(task)}

    if operation == VerificationOperation.ITEM_UPDATE:
        submission = VerificationItemJobSubmission.model_validate(data)
        task = update_verification_item(
            job,
            submission.context.id,
            submission.item_id,
            submission.status,
            submission.context,
        )
        return {"task": _dump(task)}

    if operation == VerificationOperation.ACTION:
        submission = VerificationActionSubmission.model_validate(data)
        action = VerificationAction(submission.action)
        task = apply_verification_action(
            job,
            submission.context.id,
            action.value,
            submission.context,
        )
        return {"task": _dump(task)}

    raise ValueError(f"不支持的核实审批操作：{operation}")


def _dump(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json", by_alias=True)
