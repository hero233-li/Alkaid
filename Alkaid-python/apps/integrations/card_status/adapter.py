import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.integrations.card_status.mock_store import CARD_MOCK_STORE
from apps.integrations.card_status.models import CardActionResult, CardRecord
from apps.jobs.models import Job

logger = logging.getLogger(__name__)


class CardStatusAdapter:
    def __init__(self, job: Job) -> None:
        self.job = job

    def search(self, environment: str, customer_no: str) -> tuple[CardRecord, ...]:
        self._require_mock_mode()
        logger.info(
            "card_status_mock_search",
            extra={
                "job_id": self.job.id,
                "trace_id": self.job.trace_id,
                "environment": environment,
            },
        )
        return CARD_MOCK_STORE.search(environment, customer_no)

    def apply_action(
        self,
        card_no: str,
        action: str,
        *,
        environment: str,
        customer_no: str,
        amount: float | None,
        target_card: str | None = None,
    ) -> CardActionResult:
        self._require_mock_mode()
        logger.info(
            "card_status_mock_action",
            extra={"job_id": self.job.id, "trace_id": self.job.trace_id, "action": action},
        )
        return CARD_MOCK_STORE.apply_action(
            card_no,
            action,
            environment=environment,
            customer_no=customer_no,
            amount=amount,
            target_card=target_card,
        )

    @staticmethod
    def _require_mock_mode() -> None:
        if settings.EXTERNAL_SYSTEM_MODE != "mock":
            raise ImproperlyConfigured("卡状态真实外系统 Adapter 尚未配置")
