import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.entities.user import User

logger = logging.getLogger(__name__)


class UserService:
    async def upsert_user(
        self,
        session: AsyncSession,
        entra_object_id: str,
        display_name: str,
        email: str,
    ) -> User:
        """Sync user from JWT claims into the local users table (insert or update)."""
        result = await session.execute(
            select(User).where(User.entra_object_id == entra_object_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                entra_object_id=entra_object_id,
                display_name=display_name,
                email=email,
            )
            session.add(user)
            logger.info(
                "Created new local user for entra_object_id=%s", entra_object_id
            )
        else:
            user.display_name = display_name
            user.email = email

        await session.commit()
        return user
