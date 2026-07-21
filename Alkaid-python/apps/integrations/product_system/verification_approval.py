from pydantic import BaseModel

from apps.integrations.auth import TokenManager
from apps.integrations.executor import EndpointExecutor
from apps.integrations.product_system.client import create_product_system_client
from apps.integrations.verification_approval.api import (
    SEARCH_VERIFICATION_TASK,
    action_endpoint,
    claim_endpoint,
    refresh_endpoint,
    return_endpoint,
    update_item_endpoint,
)
from apps.integrations.verification_approval.models import (
    SearchVerificationTaskRequest,
    VerificationActionRequest,
    VerificationItemUpdateRequest,
    VerificationTask,
    VerificationTaskOperationRequest,
)
from apps.jobs.http import JobHttpCallObserver
from apps.jobs.models import Job


def search_verification_task(job: Job, request: SearchVerificationTaskRequest):
    return _execute(job, SEARCH_VERIFICATION_TASK, request).data


def claim_verification_task(job: Job, task_id: str, context: VerificationTask):
    return _required(
        _execute(
            job, claim_endpoint(task_id), VerificationTaskOperationRequest(context=context)
        ).data
    )


def return_verification_task(job: Job, task_id: str, context: VerificationTask):
    return _required(
        _execute(
            job, return_endpoint(task_id), VerificationTaskOperationRequest(context=context)
        ).data
    )


def refresh_verification_task(job: Job, task_id: str, context: VerificationTask):
    return _required(
        _execute(
            job, refresh_endpoint(task_id), VerificationTaskOperationRequest(context=context)
        ).data
    )


def update_verification_item(
    job: Job, task_id: str, item_id: str, status: str, context: VerificationTask
):
    return _required(
        _execute(
            job,
            update_item_endpoint(task_id, item_id),
            VerificationItemUpdateRequest(status=status, context=context),
        ).data
    )


def apply_verification_action(job: Job, task_id: str, action: str, context: VerificationTask):
    return _required(
        _execute(
            job,
            action_endpoint(task_id, action),
            VerificationActionRequest(action=action, context=context),
        ).data
    )


def _execute(job: Job, endpoint, body: BaseModel | None):
    client = create_product_system_client("verification_approval")
    try:
        return EndpointExecutor(client, TokenManager({})).execute(
            endpoint,
            body=body,
            trace_id=job.trace_id,
            observer=JobHttpCallObserver(job, step=endpoint.operation_id),
        )
    finally:
        client.close()


def _required(task: VerificationTask | None) -> VerificationTask:
    if task is None:
        raise ValueError("核实任务不存在")
    return task
