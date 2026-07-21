from typing import Any

from apps.integrations.product_system.loan_status import apply_loan_action, search_loans
from apps.jobs.models import Job
from apps.product_data.loan_status.schemas import (
    LoanActionSubmission,
    LoanSearchSubmission,
    LoanStatusCommand,
    LoanStatusOperation,
)


def execute_loan_status(job: Job) -> dict[str, Any]:
    if "operation" in job.payload:
        command = LoanStatusCommand.model_validate(job.payload)
        operation, data = command.operation, command.data
    else:
        operation = LoanStatusOperation(job.kind.removeprefix("loan_status."))
        data = job.payload
    if operation == LoanStatusOperation.SEARCH:
        submission = LoanSearchSubmission.model_validate(data)
        return {"cards": search_loans(job, submission.environment, submission.customer_no)}
    if operation == LoanStatusOperation.ACTION:
        submission = LoanActionSubmission.model_validate(data)
        result = apply_loan_action(
            job,
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
