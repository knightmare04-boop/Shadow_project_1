"""Layer 5 of the duplicate-payment defence: a periodic sweep, not a
preventive control. If layers 1-4 (app/services/payment_service.py) ever
have a gap, this is what notices — every invoice with more than one
non-void payment is a confirmed incident, logged loudly and written to
audit_log so it surfaces in the forensic console.

Run:  python -m tools.reconcile_payments
Intended as a scheduled job (Module 8 — Uptime Kuma / cron), and as a
one-off check after any incident.
"""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import func, select

from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope
from app.models.audit import AuditLog
from app.models.payment import Payment
from app.models.types import PaymentStatus

log = get_logger(__name__)

_ACTIVE = (PaymentStatus.pending, PaymentStatus.posted, PaymentStatus.cleared)


async def reconcile() -> list[dict]:
    incidents: list[dict] = []
    async with session_scope() as db:
        rows = await db.execute(
            select(Payment.invoice_id, func.count(Payment.id).label("n"))
            .where(Payment.status.in_(_ACTIVE))
            .group_by(Payment.invoice_id)
            .having(func.count(Payment.id) > 1)
        )
        for invoice_id, n in rows.all():
            dupes = (await db.scalars(
                select(Payment).where(Payment.invoice_id == invoice_id, Payment.status.in_(_ACTIVE))
            )).all()
            incident = {
                "invoice_id": str(invoice_id),
                "n_active_payments": n,
                "payment_ids": [str(p.id) for p in dupes],
                "total_amount": str(sum(p.amount for p in dupes)),
            }
            incidents.append(incident)
            log.error("DUPLICATE_PAYMENT_INCIDENT", **incident)
            db.add(AuditLog(
                id=uuid.uuid4(), action="reconciliation.duplicate_payment_found",
                entity_type="invoice", entity_id=invoice_id, detail=incident,
            ))
    return incidents


if __name__ == "__main__":
    configure_logging(json_logs=False)
    found = asyncio.run(reconcile())
    if found:
        print(f"FOUND {len(found)} duplicate-payment incident(s) — see audit_log")
        raise SystemExit(1)
    print("reconciliation clean: no invoice has more than one active payment")
