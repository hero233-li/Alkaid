from typing import Any

from apps.integrations.product_system.card_status import apply_card_action, search_cards
from apps.jobs.models import Job
from apps.product_data.card_status.schemas import (
    CardActionSubmission,
    CardSearchSubmission,
    CardStatusCommand,
    CardStatusOperation,
)


def execute_card_status(job: Job) -> dict[str, Any]:
    if "operation" in job.payload:
        command = CardStatusCommand.model_validate(job.payload)
        operation, data = command.operation, command.data
    else:
        operation = CardStatusOperation(job.kind.removeprefix("card_status."))
        data = job.payload
    if operation == CardStatusOperation.SEARCH:
        submission = CardSearchSubmission.model_validate(data)
        cards = search_cards(job, submission.environment, submission.customer_no)
        return {"cards": [card.model_dump(mode="json", by_alias=True) for card in cards]}
    if operation == CardStatusOperation.ACTION:
        submission = CardActionSubmission.model_validate(data)
        result = apply_card_action(
            job,
            submission.card_no,
            submission.action.value,
            environment=submission.environment,
            customer_no=submission.customer_no,
            amount=submission.amount,
            target_card=submission.target_card,
        )
        return {"actionResult": result.model_dump(mode="json", by_alias=True, exclude_none=True)}
    raise ValueError(f"不支持的卡状态操作：{operation}")


def get_card_status_config() -> dict[str, object]:
    return {"environments": ["环境1", "环境2", "环境3"]}
