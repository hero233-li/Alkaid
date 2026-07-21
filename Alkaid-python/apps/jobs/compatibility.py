from datetime import date

from apps.core.errors import InvalidSubmission

LEGACY_JOB_COMPATIBILITY_UNTIL = date(2026, 10, 31)


def ensure_legacy_job_compatibility(*, today: date | None = None) -> None:
    """Reject legacy Job contracts after their documented retention window."""
    current_date = today or date.today()
    if current_date > LEGACY_JOB_COMPATIBILITY_UNTIL:
        raise InvalidSubmission(
            "旧版 Job 契约兼容期已结束，请使用 kind + payload.operation 标准契约"
        )
