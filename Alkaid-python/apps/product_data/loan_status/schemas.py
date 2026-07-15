from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class LoanStatusOperation(str, Enum):
    SEARCH = "search"
    ACTION = "action"


class LoanAction(str, Enum):
    REPAYMENT = "repayment"
    OVERDUE_REPAYMENT = "overdue-repayment"
    MATURITY_REPAYMENT = "maturity-repayment"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"
    CONTRACT_SIGN = "contract-sign"
    LOAN_DRAW = "loan-draw"


class LoanPayload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="allow")


class LoanSearchSubmission(LoanPayload):
    environment: str = Field(min_length=1, max_length=128)
    customer_no: str = Field(min_length=1, max_length=32)

    @field_validator("environment", "customer_no")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class LoanActionSubmission(LoanPayload):
    action: LoanAction
    environment: str
    customer_no: str
    card_no: str
    contract_no: str
    voucher_no: str | None = None
    amount: float | None = Field(default=None, ge=0)

    def integration_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)
