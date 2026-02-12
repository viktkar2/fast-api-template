import json

import pytest
from fastapi import Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware

import src.domain.models.entities  # noqa: F401
from src.base.config.database import Base
from src.base.models.user import User
from src.domain.auth.authorization import require_group_admin, require_superadmin


class FakeAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that sets request.state.user from X-Test-User header."""

    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("X-Test-User")
        if header:
            request.state.user = User(**json.loads(header))
        else:
            request.state.user = None
        return await call_next(request)


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(db_session_factory):
    async with db_session_factory() as session:
        yield session


@pytest.fixture
def app(db_session_factory):
    test_app = FastAPI()
    test_app.state.db_session_factory = db_session_factory
    test_app.add_middleware(FakeAuthMiddleware)

    @test_app.get("/superadmin-only")
    async def superadmin_route(user: User = Depends(require_superadmin)):
        return {"user_id": user.id}

    @test_app.get("/groups/{group_id}/admin-only")
    async def group_admin_route(
        group_id: int, user: User = Depends(require_group_admin())
    ):
        return {"user_id": user.id, "group_id": group_id}

    return test_app


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
