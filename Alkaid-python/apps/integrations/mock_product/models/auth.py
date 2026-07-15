from pydantic import BaseModel


class LoginRequest(BaseModel):
    product: str


class TokenData(BaseModel):
    token: str


class LoginResponse(BaseModel):
    data: TokenData
