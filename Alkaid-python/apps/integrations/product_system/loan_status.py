import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.integrations.loan_status.mock_store import LOAN_MOCK_STORE
from apps.jobs.models import Job

logger = logging.getLogger(__name__)


def search_loans(job: Job, environment: str, customer_no: str) -> list[dict[str, Any]]:
    _require_mock_mode()
    logger.info("loan_status_search", extra={"job_id": job.id, "trace_id": job.trace_id})
    return LOAN_MOCK_STORE.search(environment, customer_no)


def apply_loan_action(
    job: Job,
    environment: str,
    customer_no: str,
    contract_no: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    _require_mock_mode()
    logger.info(
        "loan_status_action",
        extra={"job_id": job.id, "trace_id": job.trace_id, "action": action},
    )
    return LOAN_MOCK_STORE.apply_action(environment, customer_no, contract_no, action, payload)


def _require_mock_mode() -> None:
    if settings.EXTERNAL_SYSTEM_MODE != "mock":
        raise ImproperlyConfigured("贷款状态真实外系统操作尚未配置")
