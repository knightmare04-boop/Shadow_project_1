from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.models.payment import Payment
from app.models.types import UserRoleName
from app.models.user import AppUser
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.payment_service import create_payment

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

_CAN_PAY = require_role(UserRoleName.erp_clerk, UserRoleName.system_administrator)


@router.get("", response_model=list[PaymentResponse])
async def list_payments(
    db: AsyncSession = Depends(get_db), _: AppUser = Depends(get_current_user),
    invoice_id: uuid.UUID | None = None, limit: int = 50, cursor: uuid.UUID | None = None,
) -> list[PaymentResponse]:
    stmt = select(Payment).order_by(Payment.id).limit(min(limit, 200))
    if invoice_id is not None:
        stmt = stmt.where(Payment.invoice_id == invoice_id)
    if cursor is not None:
        stmt = stmt.where(Payment.id > cursor)
    payments = (await db.scalars(stmt)).all()
    return [PaymentResponse.model_validate(p) for p in payments]


@router.post("", response_model=PaymentResponse, status_code=201)
async def post_payment(
    payload: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    actor: AppUser = Depends(_CAN_PAY),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PaymentResponse:
    # Payments are the one write path where an Idempotency-Key is not
    # optional — the whole point of layer 1 of the duplicate-payment
    # defence is that it exists BEFORE the request reaches this handler
    # (app.core.idempotency_middleware), but a client that omits the header
    # entirely bypasses that layer. Refuse rather than silently degrade to
    # layers 2-4 alone.
    if not idempotency_key:
        raise ValidationAppError(
            "payment submissions require an Idempotency-Key header",
            error_code="idempotency_key_required",
        )

    payment = await create_payment(
        db, invoice_id=payload.invoice_id, amount=payload.amount,
        payment_date=payload.payment_date, actor=actor,
    )
    await db.commit()
    await db.refresh(payment)
    return PaymentResponse.model_validate(payment)
