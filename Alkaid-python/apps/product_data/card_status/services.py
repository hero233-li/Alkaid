from typing import Any

from apps.integrations.card_status.adapter import CardStatusAdapter
from apps.jobs.models import Job
from apps.product_data.card_status.schemas import (
    CardActionSubmission,
    CardSearchSubmission,
    CardStatusOperation,
)


def execute_card_status(job: Job, operation: CardStatusOperation) -> dict[str, Any]:
    adapter = CardStatusAdapter(job)
    if operation == CardStatusOperation.SEARCH:
        submission = CardSearchSubmission.model_validate(job.payload)
        cards = adapter.search(submission.environment, submission.customer_no)
        return {"cards": [card.model_dump(mode="json", by_alias=True) for card in cards]}
    if operation == CardStatusOperation.ACTION:
        submission = CardActionSubmission.model_validate(job.payload)
        result = adapter.apply_action(
            submission.card_no,
            submission.action.value,
            amount=submission.amount,
        )
        return {"actionResult": result.model_dump(mode="json", by_alias=True, exclude_none=True)}
    raise ValueError(f"不支持的卡状态操作：{operation}")


def get_card_status_config() -> dict[str, object]:
    return {"environments": ["环境1", "环境2", "环境3"]}
