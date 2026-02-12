import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.base.config.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
