import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.integrations.card_status.mock_store import CARD_MOCK_STORE
from apps.integrations.card_status.models import CardActionResult, CardRecord
from apps.jobs.models import Job

logger = logging.getLogger(__name__)


def search_cards(job: Job, environment: str, customer_no: str) -> tuple[CardRecord, ...]:
    _require_mock_mode()
    logger.info("card_status_search", extra={"job_id": job.id, "trace_id": job.trace_id})
    return CARD_MOCK_STORE.search(environment, customer_no)


def apply_card_action(
    job: Job,
    card_no: str,
    action: str,
    *,
    environment: str,
    customer_no: str,
    amount: float | None,
    target_card: str | None = None,
) -> CardActionResult:
    _require_mock_mode()
    logger.info(
        "card_status_action",
        extra={"job_id": job.id, "trace_id": job.trace_id, "action": action},
    )
    return CARD_MOCK_STORE.apply_action(
        card_no,
        action,
        environment=environment,
        customer_no=customer_no,
        amount=amount,
        target_card=target_card,
    )


def _require_mock_mode() -> None:
    if settings.EXTERNAL_SYSTEM_MODE != "mock":
        raise ImproperlyConfigured("卡状态真实外系统操作尚未配置")
