import datetime
from typing import Annotated

from beanie import Document, Indexed
from pydantic import Field


class UserDocument(Document):
    entra_object_id: Annotated[str, Indexed(unique=True)]
    display_name: str
    email: str
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    class Settings:
        name = "users"
