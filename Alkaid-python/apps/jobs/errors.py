from apps.core.errors import ConflictError


class JobConflict(ConflictError):
    code = "job_conflict"


class InvalidJobTransition(ConflictError):
    code = "invalid_job_transition"
