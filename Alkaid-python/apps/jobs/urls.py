from django.urls import path

from apps.jobs.views import api_call_detail, cancel_job, job_detail, job_logs, retry_job

urlpatterns = [
    path("<int:job_id>", job_detail, name="job-detail"),
    path("<int:job_id>/retry", retry_job, name="job-retry"),
    path("<int:job_id>/cancel", cancel_job, name="job-cancel"),
    path("<int:job_id>/logs", job_logs, name="job-logs"),
    path("<int:job_id>/calls/<int:call_id>", api_call_detail, name="job-api-call-detail"),
]
