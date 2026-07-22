from typing import Any

from apps.core.errors import InvalidSubmission
from apps.integrations.product_system.loan_status import apply_loan_action, search_loans
from apps.jobs.commands import parse_menu_command
from apps.jobs.models import Job
from apps.product_data.loan_status.schemas import (
    LoanActionSubmission,
    LoanSearchSubmission,
    LoanStatusCommand,
    LoanStatusOperation,
)


def execute_loan_status(job: Job) -> dict[str, Any]:
    operation, data = parse_menu_command(
        job,
        prefix="loan_status",
        command_model=LoanStatusCommand,
        operation_enum=LoanStatusOperation,
    )
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
    raise InvalidSubmission(f"不支持的贷款状态操作：{operation}")


def get_loan_status_config() -> dict[str, object]:
    return {"environments": ["UAT1", "UAT2", "UATC"]}
