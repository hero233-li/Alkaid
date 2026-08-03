from django.urls import path

from apps.jobs.views import (
    api_call_detail,
    cancel_job,
    job_detail,
    job_list,
    job_logs,
    job_payload_detail,
    retry_job,
)

urlpatterns = [
    path("", job_list, name="job-list"),
    path("<int:job_id>", job_detail, name="job-detail"),
    path("<int:job_id>/payload", job_payload_detail, name="job-payload-detail"),
    path("<int:job_id>/retry", retry_job, name="job-retry"),
    path("<int:job_id>/cancel", cancel_job, name="job-cancel"),
    path("<int:job_id>/logs", job_logs, name="job-logs"),
    path("<int:job_id>/calls/<int:call_id>", api_call_detail, name="job-api-call-detail"),
]
