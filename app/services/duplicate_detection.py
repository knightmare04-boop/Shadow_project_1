"""Near-duplicate invoice detection — the SOFT signal layer, complementing
the hard partial-unique-index block on (vendor_id, invoice_number) in
Module 3. This never blocks a submission: legitimate recurring invoices
(rent, retainers, monthly service fees) look exactly like a near-duplicate
by design. It raises a review flag for a human to clear or confirm.

Signal: same vendor, invoice_date within `days_window` days of an existing
non-voided invoice, AND total_amount within `amount_tolerance_pct`% of it —
OR the invoice_number strings are highly similar (pg_trgm `similarity()`,
catches "INV-1001" vs "INV1001" typos) even if the amount differs somewhat.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import APInvoice
from app.models.types import InvoiceStatus

DEFAULT_AMOUNT_TOLERANCE_PCT = Decimal("2.0")
DEFAULT_DAYS_WINDOW = 30
SIMILARITY_THRESHOLD = 0.4


async def find_near_duplicates(
    db: AsyncSession, *, vendor_id: uuid.UUID, invoice_number: str,
    total_amount: Decimal, invoice_date: date,
    amount_tolerance_pct: Decimal = DEFAULT_AMOUNT_TOLERANCE_PCT,
    days_window: int = DEFAULT_DAYS_WINDOW,
    exclude_invoice_id: uuid.UUID | None = None,
) -> list[dict]:
    lo_date = invoice_date - timedelta(days=days_window)
    hi_date = invoice_date + timedelta(days=days_window)
    tolerance_frac = amount_tolerance_pct / Decimal(100)
    amount_lo = total_amount * (Decimal(1) - tolerance_frac)
    amount_hi = total_amount * (Decimal(1) + tolerance_frac)

    similarity_expr = func.similarity(APInvoice.invoice_number, invoice_number)

    stmt = (
        select(APInvoice, similarity_expr.label("sim"))
        .where(
            APInvoice.vendor_id == vendor_id,
            APInvoice.status != InvoiceStatus.voided,
            APInvoice.invoice_date.between(lo_date, hi_date),
            or_(
                APInvoice.total_amount.between(amount_lo, amount_hi),
                similarity_expr >= SIMILARITY_THRESHOLD,
            ),
        )
        .order_by(similarity_expr.desc())
        .limit(10)
    )
    if exclude_invoice_id is not None:
        stmt = stmt.where(APInvoice.id != exclude_invoice_id)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "candidate_invoice_id": inv.id,
            "candidate_invoice_number": inv.invoice_number,
            "similarity": round(float(sim or 0.0), 3),
            "amount_delta": abs(inv.total_amount - total_amount),
            "days_apart": abs((inv.invoice_date - invoice_date).days),
        }
        for inv, sim in rows
    ]
