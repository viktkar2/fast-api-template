import datetime

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class GroupAgentDocument(Document):
    group_id: PydanticObjectId
    agent_id: PydanticObjectId
    added_by: str
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    class Settings:
        name = "group_agents"
        indexes = [
            IndexModel(
                [("group_id", ASCENDING), ("agent_id", ASCENDING)],
                unique=True,
            ),
            IndexModel([("group_id", ASCENDING)]),
            IndexModel([("agent_id", ASCENDING)]),
        ]
