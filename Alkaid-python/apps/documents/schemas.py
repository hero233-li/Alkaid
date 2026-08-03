from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or "\x00" in cleaned:
        raise ValueError("名称不能为空，也不能包含路径分隔符")
    return cleaned


class FolderSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    parentId: str | None = Field(default=None, max_length=100)
    createdAt: datetime

    @field_validator("id")
    @classmethod
    def strip_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value)


class DocumentSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    content: str
    size: int = Field(ge=0)
    kind: str
    source: str
    folderId: str | None = Field(default=None, max_length=100)
    createdAt: datetime
    updatedAt: datetime
    lastOpenedAt: datetime

    @field_validator("id")
    @classmethod
    def strip_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        allowed = {"document", "word", "multidimensional-table", "spreadsheet"}
        if value not in allowed:
            raise ValueError("不支持的文件类型")
        return value

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        if value not in {"created", "opened"}:
            raise ValueError("不支持的文件来源")
        return value


class WorkspaceSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[DocumentSubmission] = Field(default_factory=list, max_length=5000)
    folders: list[FolderSubmission] = Field(default_factory=list, max_length=2000)


class DocumentPatchSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folderId: str | None = Field(default=None, max_length=100)
    lastOpenedAt: datetime | None = None


class FolderPatchSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    parentId: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        return _clean_name(value) if value is not None else None
