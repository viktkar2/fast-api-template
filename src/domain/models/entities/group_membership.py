import datetime

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from src.domain.models.entities.enums import GroupRole


class GroupMembershipDocument(Document):
    entra_object_id: str
    group_id: PydanticObjectId
    role: GroupRole
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    class Settings:
        name = "group_memberships"
        indexes = [
            IndexModel(
                [("entra_object_id", ASCENDING), ("group_id", ASCENDING)],
                unique=True,
            ),
            IndexModel([("entra_object_id", ASCENDING)]),
            IndexModel([("group_id", ASCENDING)]),
        ]
