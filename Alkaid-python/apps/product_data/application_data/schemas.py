from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class ApplicationDataOperation(str, Enum):
    GENERATE = "generate"


class ApplicationDataSubmission(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    environment: str = Field(min_length=1, max_length=128)
    current_date: date
    age: int = Field(ge=18, le=100)
    birth_date: date | None = None
    gender: str = Field(pattern=r"^(男|女)$")
    teller_no: str = Field(min_length=1, max_length=32)
    company_type: str = Field(pattern=r"^(91|92)$")
    count: int = Field(ge=1, le=100_000)

    @field_validator("environment", "teller_no")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ApplicationDataRecord(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)

    id: int
    environment: str
    customer_no: str
    customer_name: str
    certificate_type: str
    certificate_no: str
    card_no: str
    phone: str
    company_name: str
    company_credit_code: str
    organization_code: str
