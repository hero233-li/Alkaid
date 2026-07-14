from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class CardStatusOperation(str, Enum):
    SEARCH = "search"
    ACTION = "action"


class CardAction(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    TRANSFER = "transfer"
    CARD_PIN_RESET = "card-pin-reset"
    LOGIN_PASSWORD_RESET = "login-password-reset"


class CardPayload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class CardSearchSubmission(CardPayload):
    environment: str = Field(min_length=1, max_length=128)
    customer_no: str = Field(min_length=1, max_length=32)

    @field_validator("environment", "customer_no")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class CardActionSubmission(CardPayload):
    action: CardAction
    environment: str
    customer_no: str
    certificate_no: str | None = None
    card_no: str
    teller_no: str | None = None
    amount: float | None = Field(default=None, gt=0)
    target_card: str | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> "CardActionSubmission":
        if self.action in {CardAction.DEPOSIT, CardAction.WITHDRAW, CardAction.TRANSFER}:
            if self.amount is None or not self.teller_no:
                raise ValueError("资金操作需要金额和柜员号")
        if self.action == CardAction.TRANSFER and not self.target_card:
            raise ValueError("转账需要目标卡号")
        return self
