from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class ApplicationDataOperation(str, Enum):
    GENERATE = "generate"


class ApplicationDataSubmission(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    environment: str = Field(min_length=1, max_length=128)
    current_date: date
    age: int = Field(ge=18, le=100)
    birth_date: date
    gender: str = Field(pattern=r"^(男|女)$")
    teller_no: str = Field(min_length=1, max_length=32)
    company_type: str = Field(pattern=r"^(91|92)$")
    count: int = Field(ge=1, le=1_000)

    @field_validator("environment", "teller_no")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_birth_date_and_age(self) -> "ApplicationDataSubmission":
        from apps.mock_data.application_generator import age_on_date

        if self.birth_date > self.current_date:
            raise ValueError("出生日期不能晚于当前日期")
        if age_on_date(self.birth_date, self.current_date) != self.age:
            raise ValueError("出生日期与年龄不一致")
        return self


class ApplicationDataCommand(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    operation: ApplicationDataOperation
    data: dict[str, object]


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
    teller_no: str
    company_name: str
    company_credit_code: str
    organization_code: str
