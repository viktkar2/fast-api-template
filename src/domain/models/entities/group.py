import datetime

from beanie import Document
from pydantic import Field


class GroupDocument(Document):
    name: str
    description: str | None = None
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    class Settings:
        name = "groups"
