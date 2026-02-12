import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.base.config.database import Base


class GroupAgent(Base):
    __tablename__ = "group_agents"
    __table_args__ = (UniqueConstraint("group_id", "agent_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    added_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
