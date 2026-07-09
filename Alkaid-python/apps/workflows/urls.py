from django.urls import path

from apps.workflows.views import start_workflow, workflow_status

urlpatterns = [
    path("", start_workflow, name="workflow-start"),
    path("<uuid:workflow_id>/", workflow_status, name="workflow-status"),
]
