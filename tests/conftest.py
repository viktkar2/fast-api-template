import json

import pytest
from beanie import init_beanie
from fastapi import Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient
from starlette.middleware.base import BaseHTTPMiddleware

from src.base.models.user import User
from src.domain.auth.authorization import require_group_admin, require_superadmin
from src.domain.models.entities.agent import AgentDocument
from src.domain.models.entities.group import GroupDocument
from src.domain.models.entities.group_agent import GroupAgentDocument
from src.domain.models.entities.group_membership import GroupMembershipDocument
from src.domain.models.entities.user import UserDocument

ALL_DOCUMENTS = [
    AgentDocument,
    GroupDocument,
    GroupAgentDocument,
    GroupMembershipDocument,
    UserDocument,
]


class FakeAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that sets request.state.user from X-Test-User header."""

    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("X-Test-User")
        if header:
            request.state.user = User(**json.loads(header))
        else:
            request.state.user = None
        return await call_next(request)


@pytest.fixture(autouse=True)
async def init_db():
    """Initialize Beanie with mongomock for each test and clean up after."""
    client = AsyncMongoMockClient()
    db = client["test_db"]
    await init_beanie(database=db, document_models=ALL_DOCUMENTS)
    yield
    # Clean all collections after each test
    for doc_cls in ALL_DOCUMENTS:
        await doc_cls.find_all().delete()
    client.close()


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.add_middleware(FakeAuthMiddleware)

    @test_app.get("/superadmin-only")
    async def superadmin_route(user: User = Depends(require_superadmin)):
        return {"user_id": user.id}

    @test_app.get("/groups/{group_id}/admin-only")
    async def group_admin_route(
        group_id: str, user: User = Depends(require_group_admin())
    ):
        return {"user_id": user.id, "group_id": group_id}

    return test_app


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
