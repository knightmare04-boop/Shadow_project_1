"""Bulk-seed a realistic data volume for Module 7's query-optimization work.
EXPLAIN ANALYZE on an empty dev table proves nothing — the planner picks a
seq scan for 20 rows regardless of indexes. This generates enough rows
(default: 5,000 vendors / 40,000 invoices / 25,000 payments) for the
planner to actually choose between a seq scan and an index scan, so the
before/after numbers in Module 7 are real.

Deliberately raw SQL (COPY-style executemany), not the ORM — bulk-loading
40k+ rows through individual SQLAlchemy model instances would itself take
minutes; this is test-volume generation, not a code path under test.

Run:  python -m tools.seed_volume [--vendors 5000] [--invoices 40000] [--payments 25000]
"""
from __future__ import annotations

import argparse
import asyncio
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text

from app.core.security import hash_password
from app.db.session import session_scope
from app.models import AppUser, FiscalPeriod, GLAccount
from app.models.types import InvoiceStatus, PaymentStatus


async def seed_volume(n_vendors: int, n_invoices: int, n_payments: int) -> dict:
    rng = random.Random(42)

    async with session_scope() as db:
        user = (await db.execute(select(AppUser).limit(1))).scalar_one_or_none()
        gl = (await db.execute(select(GLAccount).limit(1))).scalar_one_or_none()
        period = (await db.execute(select(FiscalPeriod).limit(1))).scalar_one_or_none()
        if user is None or gl is None:
            raise RuntimeError("run tools/seed_core.py first (needs a user + GL account)")
        user_id, gl_id = user.id, gl.id

        # ---- vendors (bulk) ----
        vendor_rows = [
            {"id": uuid.uuid4(), "vendor_code": f"V-{i:06d}", "legal_name": f"Vendor {i:06d} Ltd",
             "tax_id": None, "bank_account_masked": None, "is_active": True, "is_blocked": False}
            for i in range(n_vendors)
        ]
        await db.execute(
            text("""INSERT INTO vendors (id, vendor_code, legal_name, tax_id, bank_account_masked, is_active, is_blocked)
                    VALUES (:id, :vendor_code, :legal_name, :tax_id, :bank_account_masked, :is_active, :is_blocked)"""),
            vendor_rows,
        )
        vendor_ids = [r["id"] for r in vendor_rows]

        # ---- invoices + lines (bulk) ----
        start = datetime.now(timezone.utc) - timedelta(days=365)
        invoice_rows, line_rows = [], []
        for i in range(n_invoices):
            inv_id = uuid.uuid4()
            vendor_id = rng.choice(vendor_ids)
            amount = Decimal(rng.randrange(5000, 500000)) / 100
            status = rng.choices(
                [InvoiceStatus.draft, InvoiceStatus.matched, InvoiceStatus.approved, InvoiceStatus.paid],
                weights=[10, 15, 15, 60],
            )[0]
            inv_date = (start + timedelta(days=rng.randrange(0, 365))).date()
            invoice_rows.append({
                "id": inv_id, "invoice_number": f"BULK-{i:07d}", "vendor_id": vendor_id,
                "purchase_order_id": None, "invoice_date": inv_date, "due_date": None,
                "total_amount": amount, "status": status.value, "match_status": "not_attempted",
                "duplicate_check_status": "clear", "duplicate_of_invoice_id": None,
                "submitted_by_id": user_id, "approved_by_id": None,
                "fiscal_period_id": period.id if period else None,
            })
            line_rows.append({
                "id": uuid.uuid4(), "invoice_id": inv_id, "line_no": 1, "po_line_id": None,
                "description": "Bulk seed line", "quantity": 1, "unit_price": amount, "gl_account_id": gl_id,
            })
        await db.execute(
            text("""INSERT INTO ap_invoices
                    (id, invoice_number, vendor_id, purchase_order_id, invoice_date, due_date,
                     total_amount, status, match_status, duplicate_check_status, duplicate_of_invoice_id,
                     submitted_by_id, approved_by_id, fiscal_period_id)
                    VALUES (:id, :invoice_number, :vendor_id, :purchase_order_id, :invoice_date, :due_date,
                            :total_amount, :status, :match_status, :duplicate_check_status, :duplicate_of_invoice_id,
                            :submitted_by_id, :approved_by_id, :fiscal_period_id)"""),
            invoice_rows,
        )
        await db.execute(
            text("""INSERT INTO ap_invoice_lines (id, invoice_id, line_no, po_line_id, description, quantity, unit_price, gl_account_id)
                    VALUES (:id, :invoice_id, :line_no, :po_line_id, :description, :quantity, :unit_price, :gl_account_id)"""),
            line_rows,
        )
        paid_invoice_ids = [r["id"] for r in invoice_rows if r["status"] == "paid"]

        # ---- payments (bulk, one per paid invoice, up to n_payments) ----
        payment_rows = []
        for inv_id in paid_invoice_ids[:n_payments]:
            inv = next(r for r in invoice_rows if r["id"] == inv_id)
            payment_rows.append({
                "id": uuid.uuid4(), "payment_run_id": None, "invoice_id": inv_id, "vendor_id": inv["vendor_id"],
                "amount": inv["total_amount"], "status": PaymentStatus.posted.value,
                "idempotency_key": None, "payment_date": inv["invoice_date"], "failure_reason": None,
            })
        if payment_rows:
            await db.execute(
                text("""INSERT INTO payments (id, payment_run_id, invoice_id, vendor_id, amount, status, idempotency_key, payment_date, failure_reason)
                        VALUES (:id, :payment_run_id, :invoice_id, :vendor_id, :amount, :status, :idempotency_key, :payment_date, :failure_reason)"""),
                payment_rows,
            )

    return {"vendors": len(vendor_rows), "invoices": len(invoice_rows), "payments": len(payment_rows)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendors", type=int, default=5000)
    ap.add_argument("--invoices", type=int, default=40000)
    ap.add_argument("--payments", type=int, default=25000)
    a = ap.parse_args()
    result = asyncio.run(seed_volume(a.vendors, a.invoices, a.payments))
    print(f"seeded: {result}")
