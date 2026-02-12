import datetime

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.base.config.database import Base
from src.domain.models.entities.enums import GroupRole


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (UniqueConstraint("entra_object_id", "group_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entra_object_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.entra_object_id"), index=True
    )
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    role: Mapped[GroupRole] = mapped_column(Enum(GroupRole))
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
