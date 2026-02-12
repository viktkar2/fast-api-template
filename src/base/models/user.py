"""
User entity module.

This module defines the User entity that represents an authenticated user
in the system, typically populated from JWT token claims.
"""

from pydantic import BaseModel, Field


class User(BaseModel):
    """
    Represents an authenticated user in the system.

    This entity is typically populated from JWT token claims and stored
    in the request state for access throughout the request lifecycle.

    Attributes:
        id: The unique identifier for the user (typically from 'oid' claim)
        email: The user's email address (from 'email' or 'preferred_username' claim)
        name: The user's display name (from 'name' claim)
        roles: List of roles assigned to the user (from 'roles' claim)
        scopes: List of scopes/permissions granted to the user (from 'scp' claim)
    """

    id: str | None = Field(
        None, description="Unique identifier for the user (Azure AD object ID)"
    )
    email: str | None = Field(
        None, description="User's email address or preferred username"
    )
    name: str | None = Field(None, description="User's display name")
    roles: list[str] = Field(
        default_factory=list, description="List of roles assigned to the user"
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="List of scopes/permissions granted to the user",
    )
    is_superadmin: bool = Field(
        default=False,
        description="Whether the user has superadmin privileges (from Entra ID role)",
    )
