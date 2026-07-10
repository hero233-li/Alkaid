from typing import Any

from pydantic import BaseModel, Field


class OperationResponse(BaseModel):
    code: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
