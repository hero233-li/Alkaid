from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class BusinessAccessOperation(str, Enum):
    SEARCH = "search"
    INVALIDATE = "invalidate"
    NOTIFICATIONS = "notifications"
    PUSH = "push"


class BusinessAccessPayload(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class BusinessAccessCommand(BusinessAccessPayload):
    operation: BusinessAccessOperation
    data: dict[str, object]


class BusinessAccessSearchSubmission(BusinessAccessPayload):
    environment: str = Field(min_length=1, max_length=128)
    name: str | None = Field(default=None, max_length=128)
    certificate_no: str | None = Field(default=None, max_length=64)

    @field_validator("environment", "name", "certificate_no")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_search_criterion(self) -> "BusinessAccessSearchSubmission":
        if not self.name and not self.certificate_no:
            raise ValueError("姓名和身份证号至少填写一个")
        return self


class BusinessAccessRecordSubmission(BusinessAccessPayload):
    record_id: int = Field(gt=0)


class BusinessAccessPushSubmission(BusinessAccessRecordSubmission):
    notification_id: int = Field(gt=0)
    version_type: str = Field(pattern=r"^(latest|previous)$")
