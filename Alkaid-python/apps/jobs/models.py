import uuid

from django.db import models


class JobStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    RETRYING = "retrying", "Retrying"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    CANCEL_REQUESTED = "cancel_requested", "Cancel requested"
    CANCELLED = "cancelled", "Cancelled"
    TIMED_OUT = "timed_out", "Timed out"


TERMINAL_JOB_STATUSES = {
    JobStatus.SUCCESS,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
    JobStatus.TIMED_OUT,
}


class Job(models.Model):
    workflow_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    kind = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=255)
    product = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(
        max_length=24,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        db_index=True,
    )
    stage = models.CharField(max_length=128, default="created")
    progress = models.PositiveSmallIntegerField(default=0)
    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    execution_config_version = models.PositiveIntegerField(default=1)
    execution_config_snapshot = models.JSONField(default=dict)
    error_message = models.TextField(blank=True, default="")
    trace_id = models.CharField(max_length=128, db_index=True)
    idempotency_key = models.CharField(max_length=128, unique=True)
    attempt_count = models.PositiveIntegerField(default=1)
    timeout_seconds = models.PositiveIntegerField(default=300)
    deadline_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"], name="job_status_exp_idx"),
            models.Index(fields=["status", "deadline_at"], name="job_status_dead_idx"),
        ]


class JobLog(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="logs")
    celery_task_id = models.CharField(max_length=128, blank=True, default="")
    attempt = models.PositiveIntegerField(default=1)
    level = models.CharField(max_length=16, default="INFO")
    step = models.CharField(max_length=128, blank=True, default="")
    message = models.TextField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["job", "id"], name="job_log_job_id_idx")]


class ApiCallStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class JobApiCall(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="api_calls")
    celery_task_id = models.CharField(max_length=128, blank=True, default="")
    attempt = models.PositiveIntegerField(default=1)
    step = models.CharField(max_length=128, blank=True, default="")
    method = models.CharField(max_length=16)
    url = models.TextField()
    request_headers = models.JSONField(default=dict)
    request_body = models.JSONField(null=True, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_headers = models.JSONField(default=dict)
    response_body = models.JSONField(null=True, blank=True)
    response_truncated = models.BooleanField(default=False)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=ApiCallStatus.choices,
        default=ApiCallStatus.RUNNING,
    )
    error_type = models.CharField(max_length=128, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["job", "id"], name="job_call_job_id_idx")]
