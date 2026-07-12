from dataclasses import replace

from apps.integrations.contracts import EndpointSpec, RetryMode
from apps.integrations.verification_approval.models import VerificationTaskResponse

SEARCH_VERIFICATION_TASK = EndpointSpec(
    operation_id="verification_approval.search",
    method="POST",
    path="/verification/tasks/search",
    response_model=VerificationTaskResponse,
    success_path="code",
    success_values=("0000",),
    retry_mode=RetryMode.SAFE,
)

CLAIM_VERIFICATION_TASK = EndpointSpec(
    operation_id="verification_approval.claim",
    method="POST",
    path="/verification/tasks/{task_id}/claim",
    response_model=VerificationTaskResponse,
    success_path="code",
    success_values=("0000",),
)

RETURN_VERIFICATION_TASK = EndpointSpec(
    operation_id="verification_approval.return",
    method="POST",
    path="/verification/tasks/{task_id}/return",
    response_model=VerificationTaskResponse,
    success_path="code",
    success_values=("0000",),
)

UPDATE_VERIFICATION_ITEM = EndpointSpec(
    operation_id="verification_approval.item.update",
    method="POST",
    path="/verification/tasks/{task_id}/items/{item_id}",
    response_model=VerificationTaskResponse,
    success_path="code",
    success_values=("0000",),
)

SUBMIT_VERIFICATION_ACTION = EndpointSpec(
    operation_id="verification_approval.action",
    method="POST",
    path="/verification/tasks/{task_id}/actions/{action}",
    response_model=VerificationTaskResponse,
    success_path="code",
    success_values=("0000",),
)


def claim_endpoint(task_id: str):
    return replace(
        CLAIM_VERIFICATION_TASK, path=CLAIM_VERIFICATION_TASK.path.format(task_id=task_id)
    )


def return_endpoint(task_id: str):
    return replace(
        RETURN_VERIFICATION_TASK,
        path=RETURN_VERIFICATION_TASK.path.format(task_id=task_id),
    )


def update_item_endpoint(task_id: str, item_id: str):
    return replace(
        UPDATE_VERIFICATION_ITEM,
        path=UPDATE_VERIFICATION_ITEM.path.format(task_id=task_id, item_id=item_id),
    )


def action_endpoint(task_id: str, action: str):
    return replace(
        SUBMIT_VERIFICATION_ACTION,
        path=SUBMIT_VERIFICATION_ACTION.path.format(task_id=task_id, action=action),
    )
