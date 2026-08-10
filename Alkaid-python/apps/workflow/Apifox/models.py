from django.db import models


class WorkbenchHistory(models.Model):
    endpoint_key = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    method = models.CharField(max_length=16)
    url = models.TextField()
    request_headers = models.JSONField(default=dict)
    request_payload = models.JSONField(default=dict)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default="")
    response_headers = models.JSONField(default=dict)
    response_body = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-updated_at", "-id"]


class WorkbenchPackage(models.Model):
    name = models.CharField(max_length=255)
    source_filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class WorkbenchPackageRequest(models.Model):
    package = models.ForeignKey(
        WorkbenchPackage,
        on_delete=models.CASCADE,
        related_name="requests",
    )
    position = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    method = models.CharField(max_length=16)
    url = models.TextField()
    request_payload = models.JSONField(default=dict)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_headers = models.JSONField(default=dict)
    response_body = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["package", "position"],
                name="workbench_pkg_request_position_uniq",
            )
        ]
