from django.contrib import admin

from apps.workflows.models import WorkflowEvent, WorkflowRun


class WorkflowEventInline(admin.TabularInline):
    model = WorkflowEvent
    extra = 0
    readonly_fields = ("step", "changed_fields", "created_at")


@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "current_step", "created_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("id", "idempotency_key")
    readonly_fields = ("id", "created_at", "updated_at", "version")
    inlines = (WorkflowEventInline,)
