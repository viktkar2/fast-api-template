from pydantic import BaseModel


class Message(BaseModel):
    message: str


class PrivateResponse(BaseModel):
    message: str
    claims: dict
