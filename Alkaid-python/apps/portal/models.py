from django.db import models


class ReleaseNote(models.Model):
    version = models.CharField(max_length=100, unique=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class PortalPreference(models.Model):
    key = models.CharField(max_length=64, unique=True)
    value = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)
