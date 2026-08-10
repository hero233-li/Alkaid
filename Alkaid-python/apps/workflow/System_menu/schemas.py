from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReleaseNoteSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("version", "content")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class MenuKeysSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    menuKeys: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("menuKeys")
    @classmethod
    def normalize_keys(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw_value in values:
            value = raw_value.strip()
            if not value or len(value) > 128 or not value.replace("-", "").isalnum():
                raise ValueError(f"菜单标识无效：{raw_value}")
            if value not in normalized:
                normalized.append(value)
        return normalized
