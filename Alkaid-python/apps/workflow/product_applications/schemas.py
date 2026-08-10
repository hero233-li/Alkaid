from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProductApplicationSubmission(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    product: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any]


class CustomerType(str, Enum):
    FARMER = "farmer"
    LEGAL_PERSON = "legal_person"
    SHAREHOLDER = "shareholder"
