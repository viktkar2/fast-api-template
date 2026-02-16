import datetime
from typing import Annotated

from beanie import Document, Indexed
from pydantic import Field


class AgentDocument(Document):
    agent_external_id: Annotated[str, Indexed(unique=True)]
    name: str
    created_by: str
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    class Settings:
        name = "agents"
