from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.gl import GLAccount
from app.models.user import AppUser
from app.schemas.gl import GLAccountResponse

router = APIRouter(prefix="/api/v1/gl-accounts", tags=["gl"])


@router.get("", response_model=list[GLAccountResponse])
async def list_gl_accounts(
    db: AsyncSession = Depends(get_db), _: AppUser = Depends(get_current_user),
) -> list[GLAccountResponse]:
    accounts = (await db.scalars(
        select(GLAccount).where(GLAccount.is_active == True).order_by(GLAccount.account_code)  # noqa: E712
    )).all()
    return [GLAccountResponse.model_validate(a) for a in accounts]
