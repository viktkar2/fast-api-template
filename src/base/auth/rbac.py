import logging
from typing import List

from fastapi import HTTPException, Request, status

from src.base.auth.auth_core import check_roles_and_scopes

logger = logging.getLogger(__name__)


def require_roles_and_scopes(
    required_roles: List[List[str]] = None, required_scopes: List[List[str]] = None
):
    """
    Dependency for FastAPI endpoints that enforces RBAC.
    """

    def checker(request: Request):
        claims = getattr(request.state, "claims", None)
        if claims is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
            )

        if not check_roles_and_scopes(claims, required_roles, required_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient roles or scopes",
            )

        return claims

    return checker
