import logging
from typing import List

from fastapi import HTTPException, Request, status

from src.base.auth.auth_core import check_roles_and_scopes
from src.base.models.role import Role
from src.base.models.user import User

logger = logging.getLogger(__name__)


def require_roles_and_scopes(
    required_roles: List[List[Role]] = None, required_scopes: List[List[str]] = None
):
    """
    Dependency for FastAPI endpoints that enforces RBAC.
    """

    def checker(request: Request):
        user: User = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
            )

        if not check_roles_and_scopes(
            user.roles, user.scopes, required_roles, required_scopes
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient roles or scopes",
            )

        return user

    return checker
