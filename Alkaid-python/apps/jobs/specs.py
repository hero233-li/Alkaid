from typing import Any, NamedTuple

from apps.jobs.compatibility import ensure_legacy_job_compatibility


class JobSpec(NamedTuple):
    task: str
    non_retryable_operations: frozenset[str] = frozenset()
    all_operations_non_retryable: bool = False


JOB_SPECS = {
    "product_application": JobSpec(
        "apps.product_data.product_applications.tasks.execute_product_application",
        all_operations_non_retryable=True,
    ),
    "application_link": JobSpec(
        "apps.product_data.application_links.tasks.execute_application_link",
        all_operations_non_retryable=True,
    ),
    "business_access": JobSpec(
        "apps.product_data.business_access.tasks.execute_business_access_task",
        frozenset({"invalidate", "push"}),
    ),
    "verification_approval": JobSpec(
        "apps.product_data.verification_approval.tasks.execute_verification_approval_task",
        frozenset({"claim", "return", "item-update", "action"}),
    ),
    "application_data": JobSpec(
        "apps.product_data.application_data.tasks.execute_application_data_task"
    ),
    "card_status": JobSpec(
        "apps.product_data.card_status.tasks.execute_card_status_task",
        frozenset({"action"}),
    ),
    "loan_status": JobSpec(
        "apps.product_data.loan_status.tasks.execute_loan_status_task",
        frozenset({"action"}),
    ),
}

LEGACY_KIND_ALIASES = {
    "application_link_generation": "application_link",
    "application_data.generate": "application_data",
}


def canonical_job_kind(kind: str) -> str:
    if kind in LEGACY_KIND_ALIASES:
        ensure_legacy_job_compatibility()
        return LEGACY_KIND_ALIASES[kind]
    if "." in kind:
        ensure_legacy_job_compatibility()
        return kind.split(".", 1)[0]
    return kind


def job_spec(kind: str) -> JobSpec:
    canonical = canonical_job_kind(kind)
    try:
        return JOB_SPECS[canonical]
    except KeyError:
        raise ValueError(f"不支持的任务类型：{kind}") from None


def is_non_retryable_job(kind: str, payload: Any) -> bool:
    try:
        spec = job_spec(kind)
    except ValueError:
        return False
    if spec.all_operations_non_retryable:
        return True
    operation = payload.get("operation") if isinstance(payload, dict) else None
    if operation is None and "." in kind:
        operation = kind.split(".", 1)[1]
    return operation in spec.non_retryable_operations
