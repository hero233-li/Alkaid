from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CardWireModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CardRecord(CardWireModel):
    environment: str
    customer_no: str
    certificate_no: str
    card_no: str
    balance: float
    status: str


class CardActionResult(CardWireModel):
    card: CardRecord
    message: str
    password: str | None = None
