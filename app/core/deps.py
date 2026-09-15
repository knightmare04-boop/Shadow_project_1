"""FastAPI dependencies: current-user resolution and RBAC gating."""
from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import AppUser
from app.models.types import UserRoleName


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> AppUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedError("invalid or expired token")

    email = payload.get("sub")
    user = await db.scalar(select(AppUser).where(AppUser.email == email))
    if user is None or not user.is_active:
        raise UnauthorizedError("user not found or inactive")
    return user


def require_role(*allowed: UserRoleName):
    """Route-level RBAC gate. Usage: ``Depends(require_role(UserRoleName.system_administrator))``."""

    async def _check(user: AppUser = Depends(get_current_user)) -> AppUser:
        if UserRoleName(user.role) not in allowed:
            raise ForbiddenError(
                f"role {user.role!r} is not permitted to perform this action",
                error_code="role_not_permitted",
            )
        return user

    return _check
