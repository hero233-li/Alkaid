from typing import Any

from apps.integrations.loan_status.adapter import LoanStatusAdapter
from apps.jobs.models import Job
from apps.product_data.loan_status.schemas import (
    LoanActionSubmission,
    LoanSearchSubmission,
    LoanStatusOperation,
)


def execute_loan_status(job: Job, operation: LoanStatusOperation) -> dict[str, Any]:
    adapter = LoanStatusAdapter(job)
    if operation == LoanStatusOperation.SEARCH:
        submission = LoanSearchSubmission.model_validate(job.payload)
        return {"cards": adapter.search(submission.environment, submission.customer_no)}
    if operation == LoanStatusOperation.ACTION:
        submission = LoanActionSubmission.model_validate(job.payload)
        result = adapter.apply_action(
            submission.environment,
            submission.customer_no,
            submission.contract_no,
            submission.action.value,
            submission.integration_payload(),
        )
        return {"actionResult": result}
    raise ValueError(f"不支持的贷款状态操作：{operation}")


def get_loan_status_config() -> dict[str, object]:
    return {"environments": ["环境1", "环境2", "环境3"]}
