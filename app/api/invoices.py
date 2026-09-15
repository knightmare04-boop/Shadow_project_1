from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, require_role
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models.invoice import APInvoice
from app.models.types import UserRoleName
from app.models.user import AppUser
from app.schemas.invoice import InvoiceCreate, InvoiceResponse
from app.services.invoice_service import create_invoice

router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])

_CAN_WRITE = require_role(UserRoleName.erp_clerk, UserRoleName.system_administrator)


@router.get("", response_model=list[InvoiceResponse])
async def list_invoices(
    db: AsyncSession = Depends(get_db), _: AppUser = Depends(get_current_user),
    vendor_id: uuid.UUID | None = None, limit: int = 50, cursor: uuid.UUID | None = None,
) -> list[InvoiceResponse]:
    stmt = select(APInvoice).options(selectinload(APInvoice.lines)).order_by(APInvoice.id).limit(min(limit, 200))
    if vendor_id is not None:
        stmt = stmt.where(APInvoice.vendor_id == vendor_id)
    if cursor is not None:
        stmt = stmt.where(APInvoice.id > cursor)
    invoices = (await db.scalars(stmt)).all()
    return [InvoiceResponse.model_validate(i) for i in invoices]


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: AppUser = Depends(get_current_user),
) -> InvoiceResponse:
    invoice = await db.scalar(
        select(APInvoice).options(selectinload(APInvoice.lines)).where(APInvoice.id == invoice_id)
    )
    if invoice is None:
        raise NotFoundError(f"invoice {invoice_id} not found")
    return InvoiceResponse.model_validate(invoice)


@router.post("", response_model=InvoiceResponse, status_code=201)
async def submit_invoice(
    payload: InvoiceCreate, db: AsyncSession = Depends(get_db), actor: AppUser = Depends(_CAN_WRITE),
) -> InvoiceResponse:
    invoice = await create_invoice(db, payload=payload, actor=actor)
    await db.commit()
    await db.refresh(invoice, attribute_names=["lines"])
    return InvoiceResponse.model_validate(invoice)
