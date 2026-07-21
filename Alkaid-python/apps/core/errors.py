class DomainError(Exception):
    """Stable business error exposed to API clients and persisted Jobs."""

    code = "domain_error"
    status_code = 400


class InvalidSubmission(DomainError):
    code = "invalid_submission"


class ConfigurationError(DomainError):
    code = "configuration_error"
    status_code = 500


class ContextIntegrityError(DomainError):
    code = "context_integrity_error"


class ConflictError(DomainError):
    code = "conflict"
    status_code = 409
