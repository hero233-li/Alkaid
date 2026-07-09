from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from pydantic import BaseModel, ConfigDict

from apps.workflows.models import WorkflowEvent, WorkflowRun, WorkflowStatus
from apps.workflows.schemas import WorkflowContext, WorkflowStartRequest


class NormalizationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str


class ValueNormalizer:
    def normalize(self, value: str) -> NormalizationResult:
        return NormalizationResult(value=" ".join(value.split()))


@dataclass(frozen=True)
class CreatedWorkflow:
    run: WorkflowRun
    created: bool


class IdempotencyConflict(ValueError):
    pass


class WorkflowRepository:
    @staticmethod
    def create(request: WorkflowStartRequest) -> CreatedWorkflow:
        context = WorkflowContext(input=request.input)
        expires_at = timezone.now() + timedelta(hours=settings.WORKFLOW_RETENTION_HOURS)
        try:
            with transaction.atomic():
                run = WorkflowRun.objects.create(
                    idempotency_key=request.idempotency_key,
                    context=context.model_dump(mode="json"),
                    expires_at=expires_at,
                )
                WorkflowEvent.objects.create(
                    workflow=run,
                    step="created",
                    changed_fields=["input", "status"],
                )
                return CreatedWorkflow(run=run, created=True)
        except IntegrityError:
            if request.idempotency_key is None:
                raise
            run = WorkflowRun.objects.get(idempotency_key=request.idempotency_key)
            existing_context = WorkflowContext.model_validate(run.context)
            if existing_context.input != request.input:
                raise IdempotencyConflict(
                    "idempotency_key already belongs to a workflow with different input"
                ) from None
            return CreatedWorkflow(run=run, created=False)

    @staticmethod
    def mark_running(workflow_id: UUID) -> WorkflowRun | None:
        with transaction.atomic():
            run = WorkflowRun.objects.select_for_update().get(id=workflow_id)
            if run.status != WorkflowStatus.PENDING:
                return None
            run.status = WorkflowStatus.RUNNING
            run.current_step = "normalize"
            run.version += 1
            run.save(update_fields=["status", "current_step", "version", "updated_at"])
            WorkflowEvent.objects.create(
                workflow=run,
                step="normalize",
                changed_fields=["status", "current_step"],
            )
            return run

    @staticmethod
    def save_context(
        workflow_id: UUID,
        *,
        context: WorkflowContext,
        step: str,
        changed_fields: tuple[str, ...],
    ) -> None:
        with transaction.atomic():
            run = WorkflowRun.objects.select_for_update().get(id=workflow_id)
            run.context = context.model_dump(mode="json")
            run.current_step = step
            run.version += 1
            run.save(update_fields=["context", "current_step", "version", "updated_at"])
            WorkflowEvent.objects.create(
                workflow=run,
                step=step,
                changed_fields=list(changed_fields),
            )

    @staticmethod
    def mark_succeeded(workflow_id: UUID) -> None:
        WorkflowRepository._finish(workflow_id, WorkflowStatus.SUCCEEDED, "completed", "")

    @staticmethod
    def mark_failed(workflow_id: UUID, error: str) -> None:
        WorkflowRepository._finish(workflow_id, WorkflowStatus.FAILED, "failed", error[:4000])

    @staticmethod
    def _finish(workflow_id: UUID, status: str, step: str, error: str) -> None:
        with transaction.atomic():
            run = WorkflowRun.objects.select_for_update().get(id=workflow_id)
            run.status = status
            run.current_step = step
            run.error = error
            run.expires_at = timezone.now() + timedelta(hours=settings.WORKFLOW_RETENTION_HOURS)
            run.version += 1
            run.save(
                update_fields=[
                    "status",
                    "current_step",
                    "error",
                    "expires_at",
                    "version",
                    "updated_at",
                ]
            )
            WorkflowEvent.objects.create(
                workflow=run,
                step=step,
                changed_fields=["status", "current_step", "error"],
            )


class WorkflowOrchestrator:
    def __init__(
        self,
        repository: WorkflowRepository | None = None,
        normalizer: ValueNormalizer | None = None,
    ) -> None:
        self.repository = repository or WorkflowRepository()
        self.normalizer = normalizer or ValueNormalizer()

    def execute(self, workflow_id: UUID) -> None:
        run = self.repository.mark_running(workflow_id)
        if run is None:
            return
        try:
            context = WorkflowContext.model_validate(run.context)
            result = self.normalizer.normalize(context.input.value)
            updated_context = context.with_normalized_value(result.value)
            self.repository.save_context(
                workflow_id,
                context=updated_context,
                step="normalized",
                changed_fields=("output.normalized_value",),
            )
            self.repository.mark_succeeded(workflow_id)
        except Exception as exc:
            self.repository.mark_failed(workflow_id, f"{type(exc).__name__}: {exc}")
            raise
