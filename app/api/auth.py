from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import RateLimitedError, UnauthorizedError
from app.core.rate_limit import check_rate_limit
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import AppUser
from app.schemas.auth import CurrentUserResponse, LoginRequest, LoginResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# 10 attempts / 5 minutes per email — enough for a legitimate user who
# mistypes a password a few times, tight enough that bcrypt's own cost
# factor (the actual expensive operation per attempt) can't be turned into
# a meaningful DoS or brute-force vector. Found and fixed following the
# Module 11 architecture review.
_LOGIN_RATE_LIMIT = 10
_LOGIN_RATE_WINDOW_SECONDS = 300


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    allowed, retry_after = await check_rate_limit(
        key=f"login:{payload.email.lower()}",
        limit=_LOGIN_RATE_LIMIT, window_seconds=_LOGIN_RATE_WINDOW_SECONDS,
    )
    if not allowed:
        raise RateLimitedError(
            f"Too many login attempts. Try again in {retry_after}s.",
            extra={"retry_after_seconds": retry_after},
        )

    user = await db.scalar(select(AppUser).where(AppUser.email == payload.email))
    # Deliberately identical error for "no such user" and "wrong password" —
    # distinguishing them lets an attacker enumerate valid emails.
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError("incorrect email or password", error_code="invalid_credentials")

    token = create_access_token(subject=user.email, role=user.role)
    return LoginResponse(access_token=token, role=user.role, full_name=user.full_name)


@router.get("/me", response_model=CurrentUserResponse)
async def me(user: AppUser = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse.model_validate(user)
