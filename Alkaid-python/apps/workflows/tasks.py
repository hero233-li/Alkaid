from uuid import UUID

from celery import shared_task
from django.utils import timezone

from apps.workflows.models import WorkflowRun, WorkflowStatus
from apps.workflows.services import WorkflowOrchestrator


@shared_task(
    name="apps.workflows.tasks.execute_workflow",
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_workflow(workflow_id: str) -> None:
    WorkflowOrchestrator().execute(UUID(workflow_id))


@shared_task(name="apps.workflows.tasks.cleanup_expired_workflows")
def cleanup_expired_workflows() -> int:
    expired = WorkflowRun.objects.filter(
        status__in=[WorkflowStatus.SUCCEEDED, WorkflowStatus.FAILED],
        expires_at__lt=timezone.now(),
    )
    run_count = expired.count()
    expired.delete()
    return run_count
