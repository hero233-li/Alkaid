from pydantic import BaseModel, ConfigDict, Field


class ExampleLookupRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str = Field(min_length=1, max_length=500)


class ExampleData(BaseModel):
    reference: str
    display_value: str


class ExampleEnvelope(BaseModel):
    data: ExampleData


class ExampleLookupResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference: str
    display_value: str
