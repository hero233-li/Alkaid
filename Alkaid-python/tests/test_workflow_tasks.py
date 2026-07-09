from datetime import timedelta

import pytest
from django.utils import timezone

from apps.workflows.models import WorkflowRun, WorkflowStatus
from apps.workflows.schemas import WorkflowInput, WorkflowStartRequest
from apps.workflows.services import ValueNormalizer, WorkflowOrchestrator, WorkflowRepository
from apps.workflows.tasks import cleanup_expired_workflows, execute_workflow


@pytest.mark.django_db(transaction=True)
def test_workflow_task_updates_typed_context_and_records_sources():
    created = WorkflowRepository.create(WorkflowStartRequest(input=WorkflowInput(value=" a   b ")))
    WorkflowRun.objects.filter(id=created.run.id).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )

    execute_workflow.run(str(created.run.id))

    run = WorkflowRun.objects.get(id=created.run.id)
    assert run.status == WorkflowStatus.SUCCEEDED
    assert run.expires_at > timezone.now() + timedelta(hours=23)
    assert run.context["output"]["normalized_value"] == "a b"
    events = list(run.events.values_list("step", "changed_fields"))
    assert ("normalized", ["output.normalized_value"]) in events


@pytest.mark.django_db(transaction=True)
def test_duplicate_task_delivery_does_not_execute_completed_workflow_twice():
    created = WorkflowRepository.create(WorkflowStartRequest(input=WorkflowInput(value="hello")))
    execute_workflow.run(str(created.run.id))
    event_count = created.run.events.count()

    execute_workflow.run(str(created.run.id))

    assert created.run.events.count() == event_count


class FailingNormalizer(ValueNormalizer):
    def normalize(self, value: str):
        raise RuntimeError("upstream failed")


@pytest.mark.django_db(transaction=True)
def test_failure_is_recorded_and_reraised():
    created = WorkflowRepository.create(WorkflowStartRequest(input=WorkflowInput(value="hello")))

    with pytest.raises(RuntimeError, match="upstream failed"):
        WorkflowOrchestrator(normalizer=FailingNormalizer()).execute(created.run.id)

    run = WorkflowRun.objects.get(id=created.run.id)
    assert run.status == WorkflowStatus.FAILED
    assert run.current_step == "failed"
    assert "upstream failed" in run.error


@pytest.mark.django_db(transaction=True)
def test_cleanup_deletes_only_expired_terminal_runs():
    expired = WorkflowRepository.create(
        WorkflowStartRequest(input=WorkflowInput(value="expired"))
    ).run
    active = WorkflowRepository.create(
        WorkflowStartRequest(input=WorkflowInput(value="active"))
    ).run
    WorkflowRun.objects.filter(id=expired.id).update(
        status=WorkflowStatus.SUCCEEDED,
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    WorkflowRun.objects.filter(id=active.id).update(
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    cleanup_expired_workflows.run()

    assert not WorkflowRun.objects.filter(id=expired.id).exists()
    assert WorkflowRun.objects.filter(id=active.id).exists()
