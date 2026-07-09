from django.contrib import admin

from apps.jobs.models import Job, JobApiCall, JobLog


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "kind", "status", "attempt_count", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("id", "workflow_id", "trace_id", "idempotency_key", "celery_task_id")
    readonly_fields = ("workflow_id", "created_at", "updated_at")


@admin.register(JobLog)
class JobLogAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "level", "step", "attempt", "created_at")
    list_filter = ("level", "step")
    search_fields = ("message", "celery_task_id")


@admin.register(JobApiCall)
class JobApiCallAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "method", "url", "status", "response_status", "duration_ms")
    list_filter = ("status", "method")
    search_fields = ("url", "celery_task_id", "error_message")
