import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.integrations.loan_status.mock_store import LOAN_MOCK_STORE
from apps.jobs.models import Job

logger = logging.getLogger(__name__)


class LoanStatusAdapter:
    def __init__(self, job: Job) -> None:
        self.job = job

    def search(self, environment: str, customer_no: str) -> list[dict[str, Any]]:
        self._require_mock_mode()
        logger.info(
            "loan_status_mock_search",
            extra={
                "job_id": self.job.id,
                "trace_id": self.job.trace_id,
                "environment": environment,
            },
        )
        return LOAN_MOCK_STORE.search(environment, customer_no)

    def apply_action(
        self,
        environment: str,
        customer_no: str,
        contract_no: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_mock_mode()
        logger.info(
            "loan_status_mock_action",
            extra={"job_id": self.job.id, "trace_id": self.job.trace_id, "action": action},
        )
        return LOAN_MOCK_STORE.apply_action(
            environment, customer_no, contract_no, action, payload
        )

    @staticmethod
    def _require_mock_mode() -> None:
        if settings.EXTERNAL_SYSTEM_MODE != "mock":
            raise ImproperlyConfigured("贷款状态真实外系统 Adapter 尚未配置")
