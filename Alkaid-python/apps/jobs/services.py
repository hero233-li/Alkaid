"""Stable public facade for Job operations.

Implementation lives in focused modules; existing imports remain compatible.
"""

from apps.jobs.creation import CreatedJob, create_job, resolve_job_identifiers
from apps.jobs.errors import InvalidJobTransition, JobConflict
from apps.jobs.job_logs import add_job_log
from apps.jobs.lifecycle import (
    mark_job_cancelled,
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    mark_job_timed_out,
    request_job_cancel,
    request_job_retry,
    update_job_progress,
)
from apps.jobs.retention import reconcile_expired_jobs
from apps.jobs.serializers import serialize_job, serialize_log

__all__ = (
    "CreatedJob",
    "InvalidJobTransition",
    "JobConflict",
    "add_job_log",
    "create_job",
    "mark_job_cancelled",
    "mark_job_failed",
    "mark_job_running",
    "mark_job_success",
    "mark_job_timed_out",
    "reconcile_expired_jobs",
    "request_job_cancel",
    "request_job_retry",
    "resolve_job_identifiers",
    "serialize_job",
    "serialize_log",
    "update_job_progress",
)
