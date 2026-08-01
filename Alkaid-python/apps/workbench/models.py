from django.db import models


class WorkbenchHistory(models.Model):
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

    class Meta:
        ordering = ["-created_at", "-id"]
