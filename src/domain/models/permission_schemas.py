from enum import Enum

from pydantic import BaseModel


class PermissionAction(str, Enum):
    ACCESS = "access"
    CREATE = "create"


class PermissionCheckResponse(BaseModel):
    allowed: bool
    role: str | None = None
