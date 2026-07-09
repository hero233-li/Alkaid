import uuid

from django.db import models


class WorkflowStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class WorkflowRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(max_length=128, unique=True, null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=WorkflowStatus.choices, default=WorkflowStatus.PENDING
    )
    current_step = models.CharField(max_length=128, default="created")
    context = models.JSONField()
    error = models.TextField(blank=True, default="")
    version = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"], name="workflow_status_exp_idx"),
        ]


class WorkflowEvent(models.Model):
    workflow = models.ForeignKey(WorkflowRun, on_delete=models.CASCADE, related_name="events")
    step = models.CharField(max_length=128)
    changed_fields = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["workflow", "created_at"], name="workflow_event_time_idx")]
