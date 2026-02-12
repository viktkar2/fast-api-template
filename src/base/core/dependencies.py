import logging
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.base.models.user import User
from src.domain.services.agent_service import AgentService
from src.domain.services.example_service import ExampleService
from src.domain.services.group_service import GroupService
from src.domain.services.membership_service import MembershipService
from src.domain.services.permission_service import PermissionService
from src.domain.services.user_service import UserService

logger = logging.getLogger(__name__)


def get_agent_service(request: Request) -> AgentService:
    """Return the singleton AgentService instance from app state."""
    return request.app.state.agent_service


def get_example_service(request: Request) -> ExampleService:
    """Return the singleton ExampleService instance from app state."""
    return request.app.state.example_service


def get_group_service(request: Request) -> GroupService:
    """Return the singleton GroupService instance from app state."""
    return request.app.state.group_service


def get_membership_service(request: Request) -> MembershipService:
    """Return the singleton MembershipService instance from app state."""
    return request.app.state.membership_service


def get_permission_service(request: Request) -> PermissionService:
    """Return the singleton PermissionService instance from app state."""
    return request.app.state.permission_service


def get_user_service(request: Request) -> UserService:
    """Return the singleton UserService instance from app state."""
    return request.app.state.user_service


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """Yield a database session from the app-level session factory."""
    async with request.app.state.db_session_factory() as session:
        yield session


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Read the authenticated user from request state and upsert into the DB."""
    user: User = request.state.user

    await user_service.upsert_user(
        session=session,
        entra_object_id=user.id,
        display_name=user.name or "",
        email=user.email or "",
    )

    return user
